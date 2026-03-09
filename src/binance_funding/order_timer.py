from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Callable


class OrderTimer:
    """
    Manages automatic order closing based on funding time.
    """
    
    def __init__(self):
        """Initialize timer manager."""
        self.scheduled_tasks: dict[str, dict] = {}
        self.background_thread = None
        self.is_running = False
    
    def schedule_close_order(
        self,
        position_id: str,
        close_after_seconds: int,
        callback: Callable,
        **callback_args
    ) -> None:
        """
        Schedule a callback to run after specified time.
        
        Args:
            position_id: Unique identifier for the position
            close_after_seconds: Seconds to wait before closing
            callback: Function to call when timer expires
            **callback_args: Arguments to pass to callback
        """
        close_time = datetime.now() + timedelta(seconds=close_after_seconds)
        
        self.scheduled_tasks[position_id] = {
            "close_time": close_time,
            "callback": callback,
            "args": callback_args,
            "executed": False,
        }
        
        print(f"⏱️  Scheduled task {position_id} to close at {close_time.isoformat()}")
    
    def schedule_funding_close(
        self,
        symbol: str,
        funding_time_unix_ms: int,
        delay_after_funding_minutes: int = 5,
        callback: Callable = None,
        **callback_args
    ) -> None:
        """
        Schedule order to close after funding payment time.
        
        Args:
            symbol: Trading symbol
            funding_time_unix_ms: Funding payment time in Unix milliseconds (from API)
            delay_after_funding_minutes: Minutes after funding to close (default 5)
            callback: Function to call when timer expires
            **callback_args: Arguments to pass to callback
        """
        # Convert Unix ms to seconds
        funding_time_unix_s = funding_time_unix_ms / 1000
        funding_datetime = datetime.fromtimestamp(funding_time_unix_s)
        close_datetime = funding_datetime + timedelta(minutes=delay_after_funding_minutes)
        
        close_after_seconds = int((close_datetime - datetime.now()).total_seconds())
        
        if close_after_seconds < 0:
            print(f"⚠️  Funding time already passed for {symbol}")
            return
        
        position_id = f"{symbol}_{int(funding_time_unix_s)}"
        self.schedule_close_order(
            position_id=position_id,
            close_after_seconds=close_after_seconds,
            callback=callback,
            symbol=symbol,
            **callback_args
        )
    
    def get_upcoming_close_times(self) -> dict[str, dict]:
        """Get all upcoming scheduled closures."""
        return {
            pos_id: {
                "close_time": task["close_time"].isoformat(),
                "seconds_remaining": max(0, int((task["close_time"] - datetime.now()).total_seconds())),
                "executed": task["executed"],
            }
            for pos_id, task in self.scheduled_tasks.items()
        }
    
    def start_background_timer(self) -> None:
        """Start background thread to monitor scheduled tasks."""
        if self.is_running:
            print("⚠️  Timer already running")
            return
        
        self.is_running = True
        self.background_thread = threading.Thread(target=self._run_timer_loop, daemon=True)
        self.background_thread.start()
        print("✅ Background timer started")
    
    def _run_timer_loop(self) -> None:
        """Background timer loop (runs in separate thread)."""
        while self.is_running:
            now = datetime.now()
            
            for position_id, task in self.scheduled_tasks.items():
                if task["executed"]:
                    continue
                
                if now >= task["close_time"]:
                    print(f"⏰ Timer expired for {position_id}! Executing callback...")
                    try:
                        task["callback"](**task["args"])
                        task["executed"] = True
                        print(f"✅ Callback executed for {position_id}")
                    except Exception as e:
                        print(f"❌ Error executing callback for {position_id}: {e}")
                        task["executed"] = True
            
            time.sleep(1)  # Check every second
    
    def stop_background_timer(self) -> None:
        """Stop background timer thread."""
        self.is_running = False
        if self.background_thread:
            self.background_thread.join(timeout=5)
        print("🛑 Background timer stopped")
    
    def cancel_scheduled_task(self, position_id: str) -> bool:
        """Cancel a scheduled task."""
        if position_id in self.scheduled_tasks:
            del self.scheduled_tasks[position_id]
            print(f"❌ Cancelled scheduled task: {position_id}")
            return True
        return False
    
    def wait_and_execute_sync(self, position_id: str) -> bool:
        """
        Synchronously wait and execute a scheduled task.
        (Blocks until task executes)
        
        Args:
            position_id: ID of the task to wait for
        
        Returns:
            True if task executed, False if not found
        """
        if position_id not in self.scheduled_tasks:
            return False
        
        task = self.scheduled_tasks[position_id]
        wait_seconds = max(0, int((task["close_time"] - datetime.now()).total_seconds()))
        
        print(f"⏳ Waiting {wait_seconds} seconds for {position_id} to close...")
        time.sleep(wait_seconds)
        
        print(f"⏰ Executing callback for {position_id}")
        try:
            task["callback"](**task["args"])
            task["executed"] = True
            print(f"✅ Task completed: {position_id}")
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            task["executed"] = True
            return False
