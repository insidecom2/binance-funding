"""
Trading Orchestration Module
=============================

This module handles automated futures-short + spot-long balance trades
for funding rate arbitrage on Binance.

Features:
- Position sizing based on account balance
- Parallel order execution (futures short + spot long)
- Real-time monitoring (basis, stop-loss, funding)
- Automatic rollback on partial fills
- P&L tracking and reporting
"""

import time
import json
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from threading import Thread
import os

logger = logging.getLogger(__name__)


class TradeExecutionError(Exception):
    """Custom exception for trading errors"""
    pass


class TradeOrchestrator:
    """
    Manages automated futures-short + spot-long balance trading
    """
    
    def __init__(self, binance_client, config: Dict[str, Any]):
        """
        Initialize trade orchestrator
        
        Args:
            binance_client: BinanceFunding client with trading methods
            config: Trading configuration dict with keys:
                - position_size (float): USD value per trade
                - leverage (float): Leverage ratio (1.0 for no leverage)
                - hedge_ratio (float): Ratio for shorts vs longs (0.5 = 50-50)
                - stop_loss_pct (float): Stop loss percentage (e.g., -0.02 for -2%)
                - exit_basis_threshold (float): Basis below which to exit
                - order_type (str): 'LIMIT' or 'MARKET'
                - trade_history_path (str): Path to persist trade history
        """
        self.client = binance_client
        self.config = config
        self.trade_history_path = config.get('trade_history_path', '.trade_history.json')
        self.active_trades = {}  # symbol -> trade info dict
        self.monitoring = False
        self.monitor_thread = None
        
    def execute_spot_futures_trade(self, opportunity: Dict[str, Any], 
                                  dry_run: bool = True) -> Dict[str, Any]:
        """
        Execute a balanced futures-short + spot-long trade
        
        Args:
            opportunity: Trade opportunity dict with keys:
                - symbol: Trading symbol (BTCUSDT, etc.)
                - funding_rate: Current funding rate
                - basis: Current basis percentage
                - predicted_next: Predicted next funding rate
                - mark_price: Mark price
            dry_run: If True, simulate trade without actual execution
            
        Returns:
            Execution result dict with:
            - success (bool)
            - symbol (str)
            - futures_order_id (str)
            - spot_order_id (str)
            - entry_price (float)
            - position_size (float)
            - futures_qty (float)
            - spot_qty (float)
            - expected_pnl (float)
            - error (str, if failed)
        """
        symbol = opportunity['symbol']
        mark_price = float(opportunity['mark_price'])
        
        logger.info(f"🟢 Starting trade execution for {symbol} (dry_run={dry_run})")
        logger.info(f"   Funding: {opportunity['funding_rate']:.6f}, Basis: {opportunity['basis']:.4f}%")
        logger.info(f"   Predicted next: {opportunity.get('predicted_next', 'N/A')}")
        
        result = {
            'symbol': symbol,
            'entry_time': datetime.now().isoformat(),
            'entry_price': mark_price,
            'success': False,
            'futures_order_id': None,
            'spot_order_id': None,
            'error': None
        }
        
        try:
            # Calculate position sizes
            futures_qty, spot_qty, expected_pnl = self._calculate_position_sizes(
                symbol, mark_price, opportunity['basis']
            )
            
            result['futures_qty'] = futures_qty
            result['spot_qty'] = spot_qty
            result['expected_pnl'] = expected_pnl
            result['position_size'] = self.config['position_size']
            
            logger.info(f"   Position sizing: futures_qty={futures_qty:.8f}, spot_qty={spot_qty:.8f}")
            logger.info(f"   Expected P&L (1 period): ${expected_pnl:.2f}")
            
            if dry_run:
                logger.info(f"   DRY RUN: Would place orders (not executing)")
                result['success'] = True
                result['futures_order_id'] = 'DRY_RUN_FUTURES'
                result['spot_order_id'] = 'DRY_RUN_SPOT'
                self._save_trade_history(result)
                return result
            
            # Place parallel orders: futures SELL (short) + spot BUY (long)
            futures_result = self._place_futures_short(symbol, futures_qty, mark_price)
            spot_result = self._place_spot_long(symbol, spot_qty, mark_price)
            
            if not futures_result['success'] or not spot_result['success']:
                logger.error(f"   ❌ Order placement failed - rolling back")
                # Attempt rollback
                if futures_result['success'] and futures_result.get('order_id'):
                    self._cancel_order(symbol, futures_result['order_id'], is_futures=True)
                if spot_result['success'] and spot_result.get('order_id'):
                    self._cancel_order(symbol, spot_result['order_id'], is_futures=False)
                
                result['error'] = f"Futures: {futures_result.get('error')}, Spot: {spot_result.get('error')}"
                self._save_trade_history(result)
                return result
            
            # Both orders succeeded
            result['success'] = True
            result['futures_order_id'] = futures_result.get('order_id')
            result['spot_order_id'] = spot_result.get('order_id')
            
            # Store active trade for monitoring
            self.active_trades[symbol] = {
                'opportunity': opportunity,
                'position': {
                    'futures_qty': futures_qty,
                    'spot_qty': spot_qty,
                    'entry_price': mark_price,
                    'futures_entry_price': futures_result.get('fill_price', mark_price),
                    'spot_entry_price': spot_result.get('fill_price', mark_price)
                },
                'order_ids': {
                    'futures': futures_result.get('order_id'),
                    'spot': spot_result.get('order_id')
                },
                'entry_time': datetime.now()
            }
            
            logger.info(f"   ✅ Trade executed successfully!")
            logger.info(f"      Futures: short {futures_qty:.8f} @ {futures_result.get('fill_price', mark_price):.2f}")
            logger.info(f"      Spot: long {spot_qty:.8f} @ {spot_result.get('fill_price', mark_price):.2f}")
            
            self._save_trade_history(result)
            return result
            
        except Exception as e:
            logger.error(f"   ❌ Trade execution error: {str(e)}")
            result['error'] = str(e)
            self._save_trade_history(result)
            return result
    
    def _calculate_position_sizes(self, symbol: str, mark_price: float, 
                                 basis: float) -> Tuple[float, float, float]:
        """
        Calculate futures short + spot long position sizes
        
        Returns:
            (futures_qty, spot_qty, expected_pnl_per_period)
        """
        position_size = self.config['position_size']
        leverage = self.config['leverage']
        hedge_ratio = self.config['hedge_ratio']  # 0.5 = 50-50
        
        # Total notional value (with leverage applied)
        total_notional = position_size * leverage
        
        # Split between shorts and longs
        short_notional = total_notional * hedge_ratio
        long_notional = total_notional * hedge_ratio
        
        # Convert to quantities (BTC/ETH/etc. quantities, not USDT)
        futures_qty = short_notional / mark_price
        spot_qty = long_notional / mark_price
        
        # Expected 1-period P&L from funding rate differential (basis %)
        # Assumption: we collect basis once = basis % of short position
        expected_pnl = short_notional * (basis / 100.0)
        
        return futures_qty, spot_qty, expected_pnl
    
    def _place_futures_short(self, symbol: str, quantity: float, 
                            entry_price: float) -> Dict[str, Any]:
        """
        Place a futures SELL (short) order
        """
        try:
            response = self.client.place_futures_order(
                symbol=symbol,
                side='SELL',
                quantity=quantity,
                order_type=self.config.get('order_type', 'LIMIT'),
                price=entry_price if self.config.get('order_type') == 'LIMIT' else None
            )
            
            # Extract order ID and fill price from response
            order_id = response.get('orderId') or response.get('clientOrderId')
            fill_price = float(response.get('avgPrice', entry_price)) if response.get('avgPrice') else entry_price
            
            return {
                'success': True,
                'order_id': order_id,
                'fill_price': fill_price,
                'response': response
            }
        except Exception as e:
            logger.error(f"Failed to place futures short for {symbol}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _place_spot_long(self, symbol: str, quantity: float, 
                        entry_price: float) -> Dict[str, Any]:
        """
        Place a spot BUY (long) order
        """
        try:
            response = self.client.place_spot_order(
                symbol=symbol,
                side='BUY',
                quantity=quantity,
                order_type=self.config.get('order_type', 'LIMIT'),
                price=entry_price if self.config.get('order_type') == 'LIMIT' else None
            )
            
            # Extract order ID and fill price from response
            order_id = response.get('orderId') or response.get('clientOrderId')
            fill_price = float(response.get('cummulativeQuoteQty', 0)) / quantity if response.get('cummulativeQuoteQty') else entry_price
            
            return {
                'success': True,
                'order_id': order_id,
                'fill_price': fill_price,
                'response': response
            }
        except Exception as e:
            logger.error(f"Failed to place spot long for {symbol}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _cancel_order(self, symbol: str, order_id: str, is_futures: bool) -> bool:
        """
        Cancel an active order
        """
        try:
            self.client.cancel_order(symbol, order_id=order_id, is_futures=is_futures)
            logger.info(f"Cancelled {'futures' if is_futures else 'spot'} order {order_id} for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {str(e)}")
            return False
    
    def start_monitoring(self, check_interval_seconds: int = 30):
        """
        Start background monitoring thread for active trades
        
        Args:
            check_interval_seconds: How often to check positions (default: 30s)
        """
        if self.monitoring:
            logger.warning("Monitoring already running")
            return
        
        self.monitoring = True
        self.monitor_thread = Thread(
            target=self._monitoring_loop,
            args=(check_interval_seconds,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Started monitoring thread (interval: {check_interval_seconds}s)")
    
    def stop_monitoring(self):
        """Stop background monitoring thread"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Stopped monitoring thread")
    
    def _monitoring_loop(self, check_interval: int):
        """
        Background loop that monitors active positions and exits on triggers
        """
        while self.monitoring:
            try:
                for symbol in list(self.active_trades.keys()):
                    trade = self.active_trades[symbol]
                    
                    # Check exit conditions
                    should_exit, reason = self._check_exit_conditions(symbol, trade)
                    
                    if should_exit:
                        logger.info(f"🔴 Exit triggered for {symbol}: {reason}")
                        exit_result = self._close_position(symbol, reason)
                        if exit_result['success']:
                            del self.active_trades[symbol]
                
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(check_interval)
    
    def _check_exit_conditions(self, symbol: str, trade: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if position should be exited
        
        Returns:
            (should_exit, reason)
        """
        try:
            # Get current position and prices
            positions = self.client.get_position_info(symbol)
            if not positions:
                return True, "Position closed by user"
            
            position = positions[0]
            current_price = float(position.get('markPrice', 0))
            entry_price = trade['position']['entry_price']
            
            # Check stop-loss
            pnl_pct = (current_price - entry_price) / entry_price
            stop_loss_pct = self.config['stop_loss_pct']
            
            if pnl_pct <= stop_loss_pct:
                return True, f"Stop-loss triggered: {pnl_pct:.2%} vs {stop_loss_pct:.2%}"
            
            # Check basis (funding rate) reversal
            # If basis goes negative/below threshold, close arbitrage
            current_premium = self.client.get_premium_index(symbol)
            if current_premium:
                current_basis = float(current_premium[0].get('lastFundingRate', 0)) * 100
                basis_threshold = self.config.get('exit_basis_threshold', 0)
                
                if current_basis < basis_threshold:
                    return True, f"Basis reversed: {current_basis:.4f}% vs threshold {basis_threshold:.4f}%"
            
            # Check if trade is old (e.g., > 1 hour) - exit anyway
            age_minutes = (datetime.now() - trade['entry_time']).total_seconds() / 60
            if age_minutes > 60:
                return True, f"Trade age limit reached: {age_minutes:.0f} minutes"
            
            return False, ""
            
        except Exception as e:
            logger.warning(f"Error checking exit conditions: {str(e)}")
            return False, ""
    
    def _close_position(self, symbol: str, exit_reason: str) -> Dict[str, Any]:
        """
        Close a position (close shorts, sell longs)
        """
        trade = self.active_trades.get(symbol)
        if not trade:
            return {'success': False, 'error': 'Trade not found'}
        
        result = {
            'symbol': symbol,
            'exit_reason': exit_reason,
            'exit_time': datetime.now().isoformat(),
            'success': False,
            'futures_close_id': None,
            'spot_close_id': None,
            'pnl': None,
            'error': None
        }
        
        try:
            position = trade['position']
            
            # Close futures short (BUY to close)
            futures_close = self.client.place_futures_order(
                symbol=symbol,
                side='BUY',
                quantity=position['futures_qty'],
                order_type=self.config.get('order_type', 'LIMIT'),
                reduce_only=True
            )
            
            # Close spot long (SELL to close)
            spot_close = self.client.place_spot_order(
                symbol=symbol,
                side='SELL',
                quantity=position['spot_qty'],
                order_type=self.config.get('order_type', 'LIMIT')
            )
            
            result['futures_close_id'] = futures_close.get('orderId')
            result['spot_close_id'] = spot_close.get('orderId')
            result['success'] = True
            
            # Calculate P&L (rough estimate from entry/exit prices)
            exit_price = float(futures_close.get('avgPrice', 0)) or position['entry_price']
            pnl = (position['entry_price'] - exit_price) * position['futures_qty']
            result['pnl'] = pnl
            
            logger.info(f"   ✅ Position closed. P&L: ${pnl:.2f}")
            
            self._save_trade_history(result)
            return result
            
        except Exception as e:
            logger.error(f"Failed to close position: {str(e)}")
            result['error'] = str(e)
            self._save_trade_history(result)
            return result
    
    def _save_trade_history(self, trade_record: Dict[str, Any]):
        """
        Persist trade record to history file
        """
        try:
            history = []
            if os.path.exists(self.trade_history_path):
                with open(self.trade_history_path, 'r') as f:
                    history = json.load(f)
            
            history.append(trade_record)
            
            with open(self.trade_history_path, 'w') as f:
                json.dump(history, f, indent=2, default=str)
            
            logger.info(f"Trade history saved to {self.trade_history_path}")
        except Exception as e:
            logger.error(f"Failed to save trade history: {str(e)}")
    
    def get_trade_pnl_summary(self) -> Dict[str, Any]:
        """
        Calculate P&L summary from trade history
        """
        try:
            if not os.path.exists(self.trade_history_path):
                return {
                    'total_trades': 0,
                    'successful_trades': 0,
                    'total_pnl': 0,
                    'average_pnl': 0,
                    'win_rate': 0
                }
            
            with open(self.trade_history_path, 'r') as f:
                history = json.load(f)
            
            closed_trades = [t for t in history if 'exit_time' in t]
            successful = [t for t in closed_trades if t.get('success')]
            
            total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
            win_count = sum(1 for t in closed_trades if t.get('pnl', 0) > 0)
            
            return {
                'total_trades': len(closed_trades),
                'successful_trades': len(successful),
                'winning_trades': win_count,
                'total_pnl': total_pnl,
                'average_pnl': total_pnl / len(closed_trades) if closed_trades else 0,
                'win_rate': (win_count / len(closed_trades) * 100) if closed_trades else 0
            }
        except Exception as e:
            logger.error(f"Error calculating P&L: {str(e)}")
            return {}
