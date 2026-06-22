export function validateEmail(email: string): boolean {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

export function validatePassword(password: string): { valid: boolean; message: string } {
  if (password.length < 8) return { valid: false, message: "密码至少 8 位" };
  if (!/[a-zA-Z]/.test(password)) return { valid: false, message: "密码需包含字母" };
  if (!/[0-9]/.test(password)) return { valid: false, message: "密码需包含数字" };
  return { valid: true, message: "" };
}

export function validatePhone(phone: string): boolean {
  return /^1[3-9]\d{9}$/.test(phone);
}
