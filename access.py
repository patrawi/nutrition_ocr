"""Gatekeeper: only Authorized Users get past this seam.

Strangers are dropped silently — no reply, ever (deliberate: a reply
tells a scanner the bot is alive). The drop is logged at INFO, which
doubles as the one-time bootstrap: with an empty allowlist, message the
bot once, read your id from the logs, add it to AUTHORIZED_USER_IDS.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

import config

logger = logging.getLogger(__name__)


def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Drop any update that does not come from an Authorized User."""
    user = update.effective_user
    if user is not None and user.id in config.AUTHORIZED_USER_IDS:
        return
    who = user.id if user else "<none>"
    logger.info("Dropped update from unauthorized sender: %s", who)
    raise ApplicationHandlerStop
