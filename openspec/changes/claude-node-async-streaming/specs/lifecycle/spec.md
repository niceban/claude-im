# lifecycle 模块规格

## 概述

lifecycle模块负责Session生命周期与Subprocess生命周期的联动。核心任务是**修复当前Session泄漏问题**。

## 当前问题

```python
# manager.py:77 (BUG - 不杀subprocess)
def _evict_lru(self) -> None:
    session_id, session_data = self._conversation_to_session.popitem(last=False)
    self._backend.destroy_session(session_id)  # 只清理backend，不杀进程！
    # adapter.destroy_session(session_id) ← 缺失！
```

## 目标状态

```python
# manager.py destroy_session() (实现后)
def destroy_session(self, session_id: str) -> None:
    # 1. 清理backend状态
    self._backend.destroy_session(session_id)

    # 2. 清理subprocess（关键！）
    adapter = get_process_manager()
    adapter.destroy_session(session_id)

def _evict_lru(self) -> None:
    session_id, session_data = self._conversation_to_session.popitem(last=False)
    self.destroy_session(session_id)  # 统一入口，同时清理两者
```

## 问题分析

### 为什么当前会泄漏

```
LRU驱逐流程：
1. popitem(last=False) 移除最老session
2. backend.destroy_session() 只标记alive=False
3. subprocess继续运行 ← 泄漏！
4. adapter._controllers[session_id]还在字典里
```

### 修复方案

```python
class SessionMappingManager:
    def __init__(self):
        self._backend = InMemorySessionBackend()
        self._adapter = get_process_manager()  # ← 添加adapter引用

    def destroy_session(self, session_id: str):
        # 同时清理两个层
        self._backend.destroy_session(session_id)
        self._adapter.destroy_session(session_id)  # ← 杀subprocess
```

## 接口规格

### destroy_session(session_id)

**行为**:
1. 从_conversation_to_session移除
2. 调用backend.destroy_session(session_id)
3. 调用adapter.destroy_session(session_id) ← 关键

### _evict_lru()

**触发条件**: session数量 > MAX_POOL_SIZE

**行为**:
1. popitem(last=False) 获取最老session
2. 调用destroy_session(session_id)

### cleanup_idle_sessions()

**触发条件**: 超过IDLE_TIMEOUT(30min)未使用

**行为**:
1. 遍历所有session
2. 检查last_used + IDLE_TIMEOUT < now
3. 调用destroy_session(session_id)

## 测试要求

1. **测试3.1.1**: destroy_session同时清理backend和subprocess
2. **测试3.1.2**: LRU驱逐时subprocess被kill
3. **测试3.1.3**: idle timeout时subprocess被kill
4. **测试3.1.4**: SIGTERM触发graceful shutdown
5. **测试3.1.5**: zombie subprocess检测和清理

## SIGTERM处理

```python
# main.py
def signal_handler(signum, frame):
    # 清理所有session
    session_manager = get_session_manager()
    for session_id in list(session_manager._conversation_to_session.keys()):
        session_manager.destroy_session(session_id)
    shutdown_all()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
```

## Zombie Reaping

subprocess可能因SIGTERM未送达或crash而变成zombie。需要定期检测和清理：

```python
class AdapterProcessManager:
    def _start_zombie_reaper(self):
        """启动zombie检测线程"""
        def check_loop():
            while True:
                time.sleep(60)  # 每60秒检测
                self._reap_zombies()

        thread = threading.Thread(target=check_loop, daemon=True)
        thread.start()

    def _is_process_alive(self, pid: int) -> bool:
        """检测进程是否存活"""
        try:
            os.kill(pid, 0)  # 信号0不发送任何信号，但能检测进程是否存在
            return True
        except ProcessLookupError:
            return False  # 进程不存在

    def _reap_zombies(self):
        """检测并清理zombie subprocess"""
        for pid in list(self._active_pids):
            if not self._is_process_alive(pid):
                self._cleanup_dead_process(pid)
                self._active_pids.discard(pid)
```

## 验收标准

- [ ] destroy_session同时杀subprocess
- [ ] LRU驱逐时无subprocess泄漏
- [ ] idle timeout时无subprocess泄漏
- [ ] SIGTERM优雅退出
- [ ] zombie subprocess定期清理
- [ ] 所有测试通过
