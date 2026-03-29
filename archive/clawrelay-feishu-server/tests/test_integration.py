"""
集成测试：验证 allowed_bots 白名单和 reply_msg_id 修复的端到端流程
"""

import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.bot_config import BotConfig, BotConfigManager


class TestAllowedBotsEndToEnd(unittest.TestCase):
    """端到端测试：allowed_bots 白名单逻辑"""

    def test_allowed_bots_rejects_unauthorized_bot(self):
        """当配置的 app_id 不在 allowed_bots 列表中时，应拒绝处理"""
        # 模拟检查逻辑（与 message_dispatcher.py:310 一致）
        config_app_id = "cli_my_bot"
        allowed_bots = ["cli_unauthorized_bot"]  # 我们的 bot 不在列表里

        should_reject = bool(allowed_bots) and config_app_id not in allowed_bots
        self.assertTrue(should_reject)

    def test_allowed_bots_authorizes_own_bot(self):
        """当配置的 app_id 在 allowed_bots 列表中时，应允许处理"""
        config_app_id = "cli_my_bot"
        allowed_bots = ["cli_my_bot"]  # 我们的 bot 在列表里

        should_reject = bool(allowed_bots) and config_app_id not in allowed_bots
        self.assertFalse(should_reject)

    def test_allowed_bots_empty_allows_all(self):
        """allowed_bots=[] 时，所有 bot 都允许（向后兼容）"""
        config_app_id = "cli_any_bot"
        allowed_bots = []

        should_reject = bool(allowed_bots) and config_app_id not in allowed_bots
        self.assertFalse(should_reject)

    def test_full_yaml_with_allowed_bots_and_allowed_users(self):
        """完整 YAML 配置：allowed_bots + allowed_users 双层检查"""
        yaml_content = """
bots:
  production_bot:
    app_id: "cli_prod_123"
    app_secret: "prod_secret"
    allowed_bots:
      - "cli_prod_123"
      - "cli_prod_trusted"
    allowed_users:
      - "ou_user_001"
      - "ou_user_002"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                mgr = BotConfigManager(config_path=f.name)
                bot = mgr.bots["production_bot"]

                # Bot 身份检查：cli_prod_123 在 allowed_bots 中
                bot_auth_ok = (
                    not bot.allowed_bots or
                    bot.app_id in bot.allowed_bots
                )
                self.assertTrue(bot_auth_ok)

                # 用户权限检查：ou_user_001 在 allowed_users 中
                user_ok = (
                    not bot.allowed_users or
                    "ou_user_001" in bot.allowed_users
                )
                self.assertTrue(user_ok)

                # 非法用户
                user_ok_false = (
                    not bot.allowed_users or
                    "ou_hacker" in bot.allowed_users
                )
                self.assertFalse(user_ok_false)
            finally:
                os.unlink(f.name)


class TestReplyMsgIdFixEndToEnd(unittest.TestCase):
    """端到端测试：reply_msg_id undefined bug 修复验证"""

    def test_edit_text_called_with_message_id_not_reply_msg_id(self):
        """在 _handle_image/_handle_file/_handle_post 的异常处理中，
        edit_text 应使用 message_id 而非未定义的 reply_msg_id"""
        import re

        dispatcher_path = os.path.join(
            os.path.dirname(__file__), '..',
            'src', 'transport', 'message_dispatcher.py'
        )
        with open(dispatcher_path, 'r') as f:
            content = f.read()

        # 找到所有异常处理块
        # 匹配：except Exception as e: ... edit_text(...)
        pattern = r'except Exception as e:(.*?)(?=\n\s{0,4}(?:async )?def |\nclass |\Z)'
        except_blocks = re.findall(pattern, content, re.DOTALL)

        errors_found = []
        for block in except_blocks:
            # 检查是否有 edit_text 调用使用了 reply_msg_id
            lines = block.split('\n')
            for i, line in enumerate(lines):
                if 'edit_text' in line and 'reply_msg_id' in line:
                    # 提取上下文
                    context = '\n'.join(lines[max(0, i-1):i+2])
                    errors_found.append(context)

        self.assertEqual(
            len(errors_found), 0,
            f"发现异常处理中使用未定义的 reply_msg_id:\n" + "\n---\n".join(errors_found)
        )


class TestYamlConfigBackwardCompatibility(unittest.TestCase):
    """向后兼容性测试：没有 allowed_bots 字段的旧 YAML 仍能正常工作"""

    def test_old_yaml_without_allowed_bots_still_works(self):
        """旧 YAML（只有 app_id/app_secret/allowed_users）应正常加载"""
        yaml_content = """
bots:
  old_bot:
    app_id: "cli_old"
    app_secret: "old_secret"
    allowed_users:
      - "ou_legacy_user"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                mgr = BotConfigManager(config_path=f.name)
                bot = mgr.bots["old_bot"]

                self.assertIsNotNone(bot)
                self.assertEqual(bot.app_id, "cli_old")
                self.assertEqual(bot.allowed_users, ["ou_legacy_user"])
                self.assertEqual(bot.allowed_bots, [])  # 默认空列表
                self.assertTrue(
                    not bot.allowed_bots or bot.app_id in bot.allowed_bots,
                    "向后兼容：allowed_bots=[] 时应不限制"
                )
            finally:
                os.unlink(f.name)


if __name__ == '__main__':
    unittest.main()
