import logging
from typing import Dict, Any

logger = logging.getLogger("InstaShelf.tools.notification")

async def notify_user_tool(bot: Any, chat_id: int, message: str) -> Dict[str, Any]:
    """
    Tool: notify_user
    Input: Telegram Bot instance, Chat ID, and markdown message
    Output: Delivery status
    """
    if not bot or not chat_id:
        logger.info(f"Notification skipped (No active chat_id). Message: {message[:100]}...")
        return {"success": True, "delivered": False, "reason": "No chat_id provided"}

    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        return {"success": True, "delivered": True}
    except Exception as e:
        logger.warning(f"Telegram notification failed (retrying without Markdown): {e}")
        try:
            await bot.send_message(chat_id=chat_id, text=message)
            return {"success": True, "delivered": True}
        except Exception as retry_err:
            logger.error(f"Telegram notification retry failed: {retry_err}")
            return {"success": False, "error": str(retry_err)}
