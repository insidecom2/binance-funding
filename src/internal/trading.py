from typing import Dict, Any, Optional


class TradeOrchestrator:
    """
    Manages automated futures-short + spot-long balance trading
    """

    def _wait_for_order_filled(self, symbol: str, order_id: str, is_futures: bool, timeout: int = 30, poll_interval: float = 1.5) -> Dict[str, Any]:
        """
        Poll order status until FILLED, PARTIALLY_FILLED, or timeout. Returns order status dict.
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                order = self.client.get_order(symbol, order_id=order_id, is_futures=is_futures)
                status = order.get('status', '').upper()
                if status in {'FILLED', 'PARTIALLY_FILLED', 'CANCELED', 'REJECTED', 'EXPIRED'}:
                    return order
            except Exception as e:
                logger.warning(f"Order status poll failed: {e}")
            time.sleep(poll_interval)
        # Final fetch after timeout
        try:
            order = self.client.get_order(symbol, order_id=order_id, is_futures=is_futures)
            return order
        except Exception as e:
            logger.error(f"Final order status fetch failed: {e}")
            return {'status': 'UNKNOWN', 'error': str(e)}

    def _retry_order_until_filled(self, place_order_fn, symbol, qty, price, is_futures, max_retries=2, timeout=30, poll_interval=1.5):
        attempts = 0
        filled_qty = 0.0
        order_ids = []
        while attempts <= max_retries:
            result = place_order_fn(symbol, qty, price)
            if not result['success']:
                logger.error(f"Order attempt {attempts+1} failed: {result.get('error')}")
                break
            order_id = result.get('order_id')
            order_ids.append(order_id)
            status = self._wait_for_order_filled(symbol, order_id, is_futures, timeout, poll_interval)
            order_status = status.get('status', '').upper()
            executed_qty = float(status.get('executedQty', 0) or status.get('executed_quantity', 0) or 0)
            filled_qty += executed_qty
            if order_status == 'FILLED':
                return {'success': True, 'order_ids': order_ids, 'filled_qty': filled_qty, 'status': order_status, 'fill_price': result.get('fill_price', price)}
            elif order_status == 'PARTIALLY_FILLED':
                logger.warning(f"Order {order_id} partially filled: {executed_qty}, retrying for remainder...")
                # Cancel remaining
                self._cancel_order(symbol, order_id, is_futures)
                qty -= executed_qty
                if qty <= 0:
                    return {'success': True, 'order_ids': order_ids, 'filled_qty': filled_qty, 'status': 'FILLED', 'fill_price': result.get('fill_price', price)}
            else:
                logger.error(f"Order {order_id} not filled: {order_status}")
                break
            attempts += 1
        return {'success': False, 'order_ids': order_ids, 'filled_qty': filled_qty, 'status': 'FAILED'}

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
        self.mysql_trades_enabled = bool(config.get('mysql_trades_enabled', False))
        self.mysql_trade_config = {
            'host': config.get('mysql_host', '127.0.0.1'),
            'port': int(config.get('mysql_port', 3306)),
            'user': config.get('mysql_user', ''),
            'password': config.get('mysql_password', ''),
            'database': config.get('mysql_database', ''),
            'table_name': config.get('mysql_table_trade_history', 'trade_history'),
        }
        self.active_trades = {}  # symbol -> trade info dict
        self.monitoring = False
        self.monitor_thread = None

    def get_unrealized_pnl(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute unrealized PnL for all or a specific open trade.
        Returns a dict: {symbol: {'unrealized_pnl': float, 'entry_price': float, 'current_price': float, ...}}
        """
        results = {}
        symbols = [symbol] if symbol else list(self.active_trades.keys())
        for sym in symbols:
            trade = self.active_trades.get(sym)
            if not trade:
                continue
            position = trade['position']
            entry_price = position.get('entry_price')
            futures_qty = position.get('futures_qty')
            # Get current mark price
            try:
                premium = self.client.get_premium_index(sym)
                if premium:
                    current_price = float(premium[0].get('markPrice', entry_price))
                else:
                    current_price = entry_price
            except Exception:
                current_price = entry_price
            # Unrealized PnL (futures leg only, before fees)
            unrealized_pnl = (entry_price - current_price) * futures_qty
            results[sym] = {
                'unrealized_pnl': unrealized_pnl,
                'entry_price': entry_price,
                'current_price': current_price,
                'futures_qty': futures_qty
            }
        return results
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
from uuid import uuid4

from src.internal.mysql_logger import insert_trade_history_row
from src.internal.symbol_rules import validate_order_inputs

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
        self.mysql_trades_enabled = bool(config.get('mysql_trades_enabled', False))
        self.mysql_trade_config = {
            'host': config.get('mysql_host', '127.0.0.1'),
            'port': int(config.get('mysql_port', 3306)),
            'user': config.get('mysql_user', ''),
            'password': config.get('mysql_password', ''),
            'database': config.get('mysql_database', ''),
            'table_name': config.get('mysql_table_trade_history', 'trade_history'),
        }
        self.active_trades = {}  # symbol -> trade info dict
        self.monitoring = False
        self.monitor_thread = None

    def _resolve_validation_price(self, symbol: str, fallback_price: float) -> float:
        """Get a fresh mark price for sizing checks, fallback to provided price."""
        try:
            premium = self.client.get_premium_index(symbol)
            if premium:
                mark = float(premium[0].get('markPrice', fallback_price))
                if mark > 0:
                    return mark
        except Exception as exc:
            logger.debug("Failed to refresh mark price for %s: %s", symbol, exc)
        return fallback_price
        
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
        trade_group_id = uuid4().hex
        
        logger.info(f"🟢 Starting trade execution for {symbol} (dry_run={dry_run})")
        logger.info(f"   Funding: {opportunity['funding_rate']:.6f}, Basis: {opportunity['basis']:.4f}%")
        logger.info(f"   Predicted next: {opportunity.get('predicted_next', 'N/A')}")
        
        result = {
            'trade_group_id': trade_group_id,
            'symbol': symbol,
            'entry_time': datetime.now().isoformat(),
            'entry_price': mark_price,
            'dry_run': dry_run,
            'order_type': self.config.get('order_type', 'LIMIT'),
            'funding_rate': opportunity.get('funding_rate'),
            'basis': opportunity.get('basis'),
            'risk': opportunity.get('risk'),
            'success': False,
            'futures_order_id': None,
            'spot_order_id': None,
            'error': None
        }

        # --- PHASE 8+: Robust order monitoring with retry/partial fill ---
        max_retries = self.config.get('max_order_retries', 2)
        # Futures leg
        fut = self._retry_order_until_filled(self._place_futures_short, symbol, futures_qty, futures_price, True, max_retries)
        if not fut['success']:
            logger.error(f"   ❌ Futures order failed after retries.")
            result['error'] = f"Futures order failed after retries. Filled: {fut['filled_qty']}"
            self._save_trade_history(result)
            return result
        # Spot leg
        spot = self._retry_order_until_filled(self._place_spot_long, symbol, spot_qty, spot_price, False, max_retries)
        if not spot['success']:
            logger.error(f"   ❌ Spot order failed after retries. Rolling back futures leg.")
            # Rollback futures leg if possible
            for oid in fut['order_ids']:
                self._cancel_order(symbol, oid, is_futures=True)
            result['error'] = f"Spot order failed after retries. Filled: {spot['filled_qty']}"
            self._save_trade_history(result)
            return result
        # Both orders succeeded or partially filled
        result['success'] = True
        result['futures_order_id'] = fut['order_ids'][-1] if fut['order_ids'] else None
        result['spot_order_id'] = spot['order_ids'][-1] if spot['order_ids'] else None
        result['futures_filled_qty'] = fut['filled_qty']
        result['spot_filled_qty'] = spot['filled_qty']

        # Store active trade for monitoring
        self.active_trades[symbol] = {
            'trade_group_id': trade_group_id,
            'opportunity': opportunity,
            'position': {
                'futures_qty': fut['filled_qty'],
                'spot_qty': spot['filled_qty'],
                'entry_price': futures_price,
                'futures_entry_price': fut.get('fill_price', futures_price),
                'spot_entry_price': spot.get('fill_price', spot_price)
            },
            'order_ids': {
                'futures': fut['order_ids'],
                'spot': spot['order_ids']
            },
            'entry_time': datetime.now(),
            'dry_run': dry_run,
        }

        logger.info(f"   ✅ Trade executed successfully! Futures filled: {fut['filled_qty']}, Spot filled: {spot['filled_qty']}")
        self._save_trade_history(result)
        return result
    #     logger.info(f"   Expected P&L (1 period): ${expected_pnl:.2f}")
        
    #     if dry_run:
    #         logger.info(f"   DRY RUN: Would place orders (not executing)")
    #         result['success'] = True
    #         result['futures_order_id'] = 'DRY_RUN_FUTURES'
    #         result['spot_order_id'] = 'DRY_RUN_SPOT'
    #         self._save_trade_history(result)
    #         return result
        
    #     # Place parallel orders: futures SELL (short) + spot BUY (long)
    #     futures_result = self._place_futures_short(symbol, futures_qty, futures_price)
    #     spot_result = self._place_spot_long(symbol, spot_qty, spot_price)
        
    #     if not futures_result['success'] or not spot_result['success']:
    #         logger.error(f"   ❌ Order placement failed - rolling back")
    #         # Attempt rollback
    #         if futures_result['success'] and futures_result.get('order_id'):
    #             self._cancel_order(symbol, futures_result['order_id'], is_futures=True)
    #         if spot_result['success'] and spot_result.get('order_id'):
    #             self._cancel_order(symbol, spot_result['order_id'], is_futures=False)
            
    #         result['error'] = f"Futures: {futures_result.get('error')}, Spot: {spot_result.get('error')}"
    #         self._save_trade_history(result)
    #         return result
        
    #     # Both orders succeeded
    #     result['success'] = True
    #     result['futures_order_id'] = futures_result.get('order_id')
    #     result['spot_order_id'] = spot_result.get('order_id')
        
    #     # Store active trade for monitoring
    #     self.active_trades[symbol] = {
    #         'trade_group_id': trade_group_id,
    #         'opportunity': opportunity,
    #         'position': {
    #             'futures_qty': futures_qty,
    #             'spot_qty': spot_qty,
    #                 'entry_price': futures_price,
    #                 'futures_entry_price': futures_result.get('fill_price', futures_price),
    #                 'spot_entry_price': spot_result.get('fill_price', spot_price)
    #         },
    #         'order_ids': {
    #             'futures': futures_result.get('order_id'),
    #             'spot': spot_result.get('order_id')
    #         },
    #         'entry_time': datetime.now(),
    #         'dry_run': dry_run,
    #     }
        
    #     logger.info(f"   ✅ Trade executed successfully!")
    #     logger.info(f"      Futures: short {futures_qty:.8f} @ {futures_result.get('fill_price', mark_price):.2f}")
    #     logger.info(f"      Spot: long {spot_qty:.8f} @ {spot_result.get('fill_price', spot_price):.2f}")
        
    #     self._save_trade_history(result)
    #     return result
        
    # except Exception as e:
    #     logger.error(f"   ❌ Trade execution error: {str(e)}")
    #     result['error'] = str(e)
    #     self._save_trade_history(result)
    #     return result
    
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
                        # แจ้งเตือน Telegram เมื่อ auto-close
                        try:
                            from cmd.main import send_telegram_message
                            msg = (
                                f"[Auto-Close] {symbol}\n"
                                f"เหตุผล: {reason}\n"
                                f"exit_time: {exit_result.get('exit_time')}\n"
                                f"pnl: {exit_result.get('pnl')}"
                            )
                            send_telegram_message(msg)
                        except Exception as e:
                            logger.warning(f"Telegram notify failed: {e}")
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
            'trade_group_id': trade.get('trade_group_id'),
            'symbol': symbol,
            'exit_reason': exit_reason,
            'exit_time': datetime.now().isoformat(),
            'entry_time': trade.get('entry_time').isoformat() if isinstance(trade.get('entry_time'), datetime) else None,
            'dry_run': bool(trade.get('dry_run', False)),
            'order_type': self.config.get('order_type', 'LIMIT'),
            'funding_rate': (trade.get('opportunity') or {}).get('funding_rate'),
            'basis': (trade.get('opportunity') or {}).get('basis'),
            'risk': (trade.get('opportunity') or {}).get('risk'),
            'success': False,
            'futures_close_id': None,
            'spot_close_id': None,
            'pnl': None,
            'error': None
        }
        
        try:
            position = trade['position']
            reference_price = self._resolve_validation_price(symbol, float(position.get('entry_price', 0)))
            order_type = self.config.get('order_type', 'LIMIT')

            futures_close_validation = validate_order_inputs(
                symbol=symbol,
                market='futures',
                side='BUY',
                quantity=position['futures_qty'],
                price=reference_price,
                filters=self.client.get_symbol_filters(symbol, is_futures=True),
                order_type=order_type,
            )
            if not futures_close_validation['ok']:
                reason = futures_close_validation['reason']
                logger.warning(
                    "Rejected %s futures close sizing: %s | rounded_qty=%s price=%s notional=%.8f",
                    symbol,
                    reason,
                    futures_close_validation['quantity_str'],
                    futures_close_validation['price_str'],
                    futures_close_validation['notional'],
                )
                result['error'] = f"Futures close sizing rejected: {reason}"
                self._save_trade_history(result)
                return result

            spot_close_validation = validate_order_inputs(
                symbol=symbol,
                market='spot',
                side='SELL',
                quantity=position['spot_qty'],
                price=reference_price,
                filters=self.client.get_symbol_filters(symbol, is_futures=False),
                order_type=order_type,
            )
            if not spot_close_validation['ok']:
                reason = spot_close_validation['reason']
                logger.warning(
                    "Rejected %s spot close sizing: %s | rounded_qty=%s price=%s notional=%.8f",
                    symbol,
                    reason,
                    spot_close_validation['quantity_str'],
                    spot_close_validation['price_str'],
                    spot_close_validation['notional'],
                )
                result['error'] = f"Spot close sizing rejected: {reason}"
                self._save_trade_history(result)
                return result
            
            # Close futures short (BUY to close)
            futures_close = self.client.place_futures_order(
                symbol=symbol,
                side='BUY',
                quantity=futures_close_validation['quantity'],
                order_type=self.config.get('order_type', 'LIMIT'),
                price=futures_close_validation['price'] if order_type == 'LIMIT' else None,
                reduce_only=True
            )
            
            # Close spot long (SELL to close)
            spot_close = self.client.place_spot_order(
                symbol=symbol,
                side='SELL',
                quantity=spot_close_validation['quantity'],
                order_type=self.config.get('order_type', 'LIMIT'),
                price=spot_close_validation['price'] if order_type == 'LIMIT' else None,
            )
            
            result['futures_close_id'] = futures_close.get('orderId')
            result['spot_close_id'] = spot_close.get('orderId')
            result['success'] = True
            result['futures_qty'] = position.get('futures_qty')
            result['spot_qty'] = position.get('spot_qty')
            result['position_size'] = self.config.get('position_size')
            result['entry_price'] = position.get('entry_price')
            
            # Calculate P&L (rough estimate from entry/exit prices)
            exit_price = float(futures_close.get('avgPrice', 0)) or position['entry_price']
            raw_pnl = (position['entry_price'] - exit_price) * position['futures_qty']

            # --- Fee Calculation ---
            # Use config or default fee rates (e.g., 0.04% per trade)
            fee_rate_futures = self.config.get('fee_rate_futures', 0.0004)  # 0.04%
            fee_rate_spot = self.config.get('fee_rate_spot', 0.0004)        # 0.04%

            # Fees are charged on notional value of each leg (entry + exit)
            notional_futures = abs(position['entry_price'] * position['futures_qty'])
            notional_spot = abs(position['entry_price'] * position['spot_qty'])
            # For closing, use exit price for both legs
            notional_futures_exit = abs(exit_price * position['futures_qty'])
            notional_spot_exit = abs(exit_price * position['spot_qty'])

            fee_futures = (notional_futures + notional_futures_exit) * fee_rate_futures
            fee_spot = (notional_spot + notional_spot_exit) * fee_rate_spot
            fee_total = fee_futures + fee_spot

            pnl = raw_pnl - fee_total
            result['pnl'] = pnl
            result['fee_futures'] = fee_futures
            result['fee_spot'] = fee_spot
            result['fee_total'] = fee_total

            logger.info(f"   ✅ Position closed. P&L: ${pnl:.2f} (raw: ${raw_pnl:.2f}, fees: ${fee_total:.2f})")

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

            if self.mysql_trades_enabled:
                user = self.mysql_trade_config.get('user')
                database = self.mysql_trade_config.get('database')
                if not user or not database:
                    logger.warning("MySQL trade logging enabled but user/database not set; skip DB insert")
                    return

                inserted = insert_trade_history_row(
                    trade_record=trade_record,
                    host=self.mysql_trade_config['host'],
                    port=self.mysql_trade_config['port'],
                    user=self.mysql_trade_config['user'],
                    password=self.mysql_trade_config['password'],
                    database=self.mysql_trade_config['database'],
                    table_name=self.mysql_trade_config['table_name'],
                )
                if inserted:
                    logger.info(
                        "Trade history inserted into MySQL table %s",
                        self.mysql_trade_config['table_name'],
                    )
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
