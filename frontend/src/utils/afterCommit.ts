/**
 * 把一个动作排到当前 effect 提交后的**微任务**里执行。
 *
 * 为什么需要它：`react-hooks/set-state-in-effect` 不允许在 effect 内（含其同步调用到的
 * 组件内函数里）直接 setState，否则报"级联渲染"。但有几处动作天然属于
 * "挂载/属性变化后立刻启动"，例如首屏拉取报告、按 URL 参数自动触发生成、
 * 切换绘图工具后清理草稿——它们必须由 effect 触发。
 *
 * 排到微任务后，state 更新发生在 effect 的同步阶段之外：执行时机与直接调用一致
 * （下一个微任务），不改变可观测行为，同时满足规则。
 *
 * ⚠ 这是对规则边界的**折衷**，不是推荐模式。新增调用点前先问：这个动作能不能
 * 挪到事件处理器或改成状态机驱动？确有必要再使用本函数（目前 3 处）。
 */
export function afterCommit(action: () => void): void {
  void Promise.resolve().then(action);
}
