/**
 * 合并「同一 key 的并发请求」：第一个请求还在飞时，后续调用复用同一个 Promise。
 *
 * 为什么需要：React StrictMode 在开发期会双挂载组件，挂载期发起的请求因此发两次
 * ——报告工作台首屏读报告就踩到了（控制台两行一样的 404、浏览器控制台里重复的
 * 失败请求）。合并后同一 key 只发一次。
 *
 * 只在「请求未结束」期间合并：一旦落地（成功或失败）就从表里移除，
 * 之后的调用照常发起新请求（保存后重新加载等场景拿到的仍是最新数据）。
 */
const inflight = new Map<string, Promise<unknown>>();

export function dedupeInflight<T>(key: string, factory: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key);
  if (existing) return existing as Promise<T>;

  const promise = factory();
  inflight.set(key, promise);
  const release = () => {
    if (inflight.get(key) === promise) inflight.delete(key);
  };
  // 成功与失败都释放；这里已经处理了拒绝，避免产生未处理的 rejection
  void promise.then(release, release);
  return promise;
}

/** 仅供测试：清空在途表，避免用例之间互相污染 */
export function resetInflight(): void {
  inflight.clear();
}
