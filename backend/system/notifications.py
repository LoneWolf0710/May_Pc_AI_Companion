"""Windows Toast Notification system for May AI Companion.

Uses winotify for native Windows 10/11 toast notifications.
Includes a background reminder checker that polls for due reminders.
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("may.notifications")


def send_toast(title: str, message: str, icon: str | None = None) -> bool:
    """Send a Windows toast notification.

    Args:
        title: Notification title
        message: Notification body text
        icon: Optional path to icon file

    Returns:
        True if notification was sent, False otherwise
    """
    try:
        from winotify import Notification

        toast = Notification(
            app_id="May AI Companion",
            title=title,
            msg=message,
            duration="short",
        )
        if icon:
            toast.set_audio(default=False)
            toast.icon = icon

        toast.show()
        return True
    except ImportError:
        logger.warning("winotify not installed. Run: pip install winotify")
        return False
    except Exception as e:
        logger.error(f"Failed to send toast: {e}")
        return False


def send_reminder_toast(reminder_message: str, reminder_id: int) -> bool:
    """Send a reminder notification.

    Args:
        reminder_message: The reminder text
        reminder_id: The reminder ID (for marking as complete)

    Returns:
        True if notification was sent
    """
    return send_toast(
        title="🌸 May Reminder",
        message=reminder_message,
    )


async def check_and_send_reminders(fact_store) -> list[dict]:
    """Check for due reminders and send notifications.

    Args:
        fact_store: The FactStore instance to check reminders

    Returns:
        List of reminders that were sent
    """
    pending = fact_store.get_pending_reminders()
    now = datetime.now()
    sent = []

    for reminder in pending:
        try:
            remind_at_str = reminder.get("remind_at", "")
            if not remind_at_str:
                continue

            remind_at = datetime.fromisoformat(remind_at_str)
            if now >= remind_at:
                # Send the notification
                message = reminder.get("message", "Reminder from May~")
                reminder_id = reminder.get("id")

                success = send_reminder_toast(message, reminder_id)
                if success:
                    # Mark as completed
                    fact_store.complete_reminder(reminder_id)
                    sent.append({
                        "id": reminder_id,
                        "message": message,
                        "remind_at": remind_at_str,
                    })
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to process reminder: {e}")
            continue

    return sent


class ReminderChecker:
    """Background task that periodically checks for due reminders."""

    def __init__(self, fact_store, check_interval: float = 30.0):
        """Initialize the reminder checker.

        Args:
            fact_store: The FactStore instance
            check_interval: How often to check (in seconds)
        """
        self.fact_store = fact_store
        self.check_interval = check_interval
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Start the background reminder checker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info(f"Reminder checker started (interval: {self.check_interval}s)")

    async def stop(self):
        """Stop the background reminder checker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Reminder checker stopped")

    async def _check_loop(self):
        """Main check loop."""
        while self._running:
            try:
                sent = await check_and_send_reminders(self.fact_store)
                if sent:
                    for r in sent:
                        logger.info(f"Reminder sent: {r['message'][:50]}")
            except Exception as e:
                logger.error(f"Reminder check error: {e}")

            await asyncio.sleep(self.check_interval)
