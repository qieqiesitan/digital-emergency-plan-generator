// 平台检测工具
// 用于在桌面端和移动端之间分发路由

export function isMobile(): boolean {
  // UA 检测
  if (/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
    return true;
  }
  // 屏幕宽度检测（平板竖屏 / 窄窗口 ≤ 768px）
  if (window.innerWidth <= 768) {
    return true;
  }
  return false;
}

export function isIOS(): boolean {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent);
}

export function isAndroid(): boolean {
  return /Android/i.test(navigator.userAgent);
}

export function isStandalone(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches;
}
