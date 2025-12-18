import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("TelegramBot")

class TelegramBot:
    def __init__(self, token=None, chat_id=None, state_provider=None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.state_provider = state_provider
        self.application = None
        
        if not self.token:
            logger.warning("Telegram Bot Token missing. Bot will be disabled.")
            return

    async def start(self):
        """Initialize and start the Telegram bot."""
        if not self.token:
            return
            
        self.application = ApplicationBuilder().token(self.token).build()
        
        # Add Handlers
        self.application.add_handler(CommandHandler("start_bot", self.cmd_start_bot))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("panic", self.cmd_panic))
        self.application.add_handler(CommandHandler("top10", self.cmd_top10))
        self.application.add_handler(CommandHandler("help", self.cmd_help))

        # Start the application
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        if self.chat_id:
            await self.send_message("🚀 Bot System Online. Type /help for commands.")
        
        logger.info("Telegram Bot started.")

    async def stop(self):
        """Stop the Telegram bot."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    async def send_message(self, text: str):
        """Send a message to the configured chat."""
        if not self.application or not self.chat_id:
            return
        try:
            await self.application.bot.send_message(chat_id=self.chat_id, text=text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    # --- Command Handlers ---

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🤖 *AI Bot Commands:*\n"
            "/status - View current PNL and bot stats\n"
            "/panic - LIQUIDATE ALL POSITIONS\n"
            "/top10 - Current Top 10 coin prices\n"
            "/start_bot - Start the trading loop (if stopped)\n"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.state_provider:
            status = self.state_provider.get_status_summary()
            await update.message.reply_text(status, parse_mode='Markdown')
        else:
            await update.message.reply_text("State provider not configured.")

    async def cmd_panic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.state_provider:
            await self.send_message("🚨 *PANIC COMMAND RECEIVED* 🚨\nLiquidation in progress...")
            success = await self.state_provider.panic_sell_all()
            if success:
                await update.message.reply_text("✅ All positions liquidated.")
            else:
                await update.message.reply_text("❌ Panic sell failed. Check logs!")
        else:
            await update.message.reply_text("State provider not configured.")

    async def cmd_top10(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.state_provider:
            prices = self.state_provider.get_top10_prices()
            await update.message.reply_text(prices, parse_mode='Markdown')
        else:
            await update.message.reply_text("State provider not configured.")

    async def cmd_start_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Feature coming soon: Remote bot restart.")
