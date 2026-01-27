"""
Prompt module for chat pipeline
"""

from .prompt import (
    TOOL_CALLING_SYSTEM_PROMPT,
    FINAL_ANSWER_SYSTEM_PROMPT_TEMPLATE,
    FINAL_ANSWER_USER_PROMPT_TEMPLATE,
    SEARCH_EMAILS_TOOL_DESCRIPTION,
    SEARCH_ATTACHMENTS_TOOL_DESCRIPTION,
    get_final_answer_system_prompt,
    get_final_answer_user_prompt,
    format_email_result,
    format_attachment_result,
)

__all__ = [
    "TOOL_CALLING_SYSTEM_PROMPT",
    "FINAL_ANSWER_SYSTEM_PROMPT_TEMPLATE",
    "FINAL_ANSWER_USER_PROMPT_TEMPLATE",
    "SEARCH_EMAILS_TOOL_DESCRIPTION",
    "SEARCH_ATTACHMENTS_TOOL_DESCRIPTION",
    "get_final_answer_system_prompt",
    "get_final_answer_user_prompt",
    "format_email_result",
    "format_attachment_result",
]
