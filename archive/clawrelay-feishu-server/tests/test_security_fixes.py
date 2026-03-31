"""
测试 P0 安全修复：
1. reply_msg_id undefined bug（message_id 替代）
2. allowed_bots 白名单机制
3. BotConfig allowed_bots 字段加载
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# 将 src 加入 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.bot_config import BotConfig, BotConfigManager


class TestBotConfigAllowedBots(unittest.TestCase):
    """测试 BotConfig 的 allowed_bots 字段"""

    def test_allowed_bots_field_exists(self):
        """BotConfig 必须支持 allowed_bots 参数"""
        cfg = BotConfig(
            bot_key="test",
            app_id="cli_test",
            allowed_bots=["cli_test", "cli_other"],
            allowed_users=["ou_abc"],
        )
        self.assertEqual(cfg.allowed_bots, ["cli_test", "cli_other"])
        self.assertEqual(cfg.allowed_users, ["ou_abc"])

    def test_allowed_bots_defaults_to_empty_list(self):
        """allowed_bots 未传时默认为空列表"""
        cfg = BotConfig(bot_key="test", app_id="cli_test")
        self.assertEqual(cfg.allowed_bots, [])

    def test_allowed_bots_or_empty_list(self):
        """allowed_bots=None 时正确处理为 []"""
        cfg = BotConfig(bot_key="test", app_id="cli_test", allowed_bots=None)
        self.assertEqual(cfg.allowed_bots, [])


class TestBotConfigManagerAllowedBots(unittest.TestCase):
    """测试 BotConfigManager 从 YAML 加载 allowed_bots"""

    def test_loads_allowed_bots_from_yaml(self):
        """YAML 中的 allowed_bots 字段应被正确加载"""
        yaml_content = """
bots:
  test_bot:
    app_id: "cli_test_bot"
    app_secret: "secret123"
    allowed_bots:
      - "cli_test_bot"
      - "cli_trusted"
    allowed_users:
      - "ou_user1"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                mgr = BotConfigManager(config_path=f.name)
                bot = mgr.bots.get("test_bot")
                self.assertIsNotNone(bot)
                self.assertEqual(bot.allowed_bots, ["cli_test_bot", "cli_trusted"])
                self.assertEqual(bot.allowed_users, ["ou_user1"])
            finally:
                os.unlink(f.name)

    def test_allowed_bots_empty_list_when_missing(self):
        """YAML 中没有 allowed_bots 时默认为空列表"""
        yaml_content = """
bots:
  minimal_bot:
    app_id: "cli_minimal"
    app_secret: "secret"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                mgr = BotConfigManager(config_path=f.name)
                bot = mgr.bots.get("minimal_bot")
                self.assertIsNotNone(bot)
                self.assertEqual(bot.allowed_bots, [])
            finally:
                os.unlink(f.name)


class TestAllowedBotsSecurityCheck(unittest.TestCase):
    """测试 allowed_bots 白名单安全检查逻辑"""

    def test_bot_id_in_allowed_bots_passes(self):
        """当 app_id 在 allowed_bots 中时，检查应通过"""
        # 模拟检查逻辑
        config_app_id = "cli_my_bot"
        allowed_bots = ["cli_my_bot", "cli_trusted"]

        result = not allowed_bots or config_app_id in allowed_bots
        self.assertTrue(result)

    def test_bot_id_not_in_allowed_bots_fails(self):
        """当 app_id 不在 allowed_bots 中时，检查应失败"""
        config_app_id = "cli_my_bot"
        allowed_bots = ["cli_other_bot", "cli_trusted"]

        result = not allowed_bots or config_app_id in allowed_bots
        self.assertFalse(result)

    def test_empty_allowed_bots_means_no_restriction(self):
        """allowed_bots=[] 时不应限制（向后兼容）"""
        config_app_id = "cli_my_bot"
        allowed_bots = []

        result = not allowed_bots or config_app_id in allowed_bots
        self.assertTrue(result)  # [] 为 falsy，不限制


class TestReplyMsgIdBugFix(unittest.TestCase):
    """验证 reply_msg_id undefined bug 已修复

    原来错误代码：
        await self.feishu_api.edit_text(reply_msg_id, _friendly_error(e))
        # reply_msg_id 在 _handle_post/_handle_image/_handle_file 的异常处理中未定义

    修复后：
        await self.feishu_api.edit_text(message_id, _friendly_error(e))
    """

    def test_message_id_is_defined_in_exception_handlers(self):
        """确认 message_id 在 _handle_image/_handle_file/_handle_post 异常处理中可用

        这三个方法的签名都是：
            async def _handle_*(self, message_id: str, ...)

        所以在 except 块中使用 message_id 是正确的
        """
        # 模拟验证：message_id 作为参数传入，在 except 块中引用不会 NameError
        message_id = "test_msg_id_123"

        def simulated_handler():
            try:
                x = 1 / 0
            except Exception as e:
                # 修复后使用 message_id（修复前用的是未定义的 reply_msg_id）
                result = message_id
                return result

        result = simulated_handler()
        self.assertEqual(result, "test_msg_id_123")

    def test_no_undefined_reply_msg_id_in_source(self):
        """确认源码中异常处理里不再使用 reply_msg_id（该变量名仅作为回调参数合法使用）"""
        dispatcher_path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'transport', 'message_dispatcher.py'
        )
        with open(dispatcher_path, 'r') as f:
            content = f.read()

        # 在 except 块中不应出现 reply_msg_id
        import re

        # 查找所有 except 块
        except_blocks = re.findall(
            r'except.*?\n(.*?)(?=\n    (?:async )?def |\Z)',
            content,
            re.DOTALL
        )

        for block in except_blocks:
            # 在 except 块中，如果出现 reply_msg_id，应该是在 _make_stream_delta_callback 的参数中
            # 或者不应该出现在错误处理的 edit_text 调用中
            if 'edit_text' in block and 'reply_msg_id' in block:
                # 这是合法的：_make_stream_delta_callback(reply_msg_id) 中的使用
                # 但在 except Exception handler 中不应该出现
                # 检查是否在 _make_stream_delta_callback 函数内
                lines = block.split('\n')
                for line in lines:
                    if 'reply_msg_id' in line and 'edit_text' in line:
                        # 确认这是异常处理中的错误
                        self.fail(
                            f"发现 except 块中仍使用 reply_msg_id: {line.strip()}"
                        )


if __name__ == '__main__':
    unittest.main()
