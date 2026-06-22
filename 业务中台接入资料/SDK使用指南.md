# 业务中台 SDK 使用指南

> yewuzhongtai-client-starter v1.0.0-SNAPSHOT

## 一、快速开始

### 1.1 Maven 依赖
```xml
<dependency>
    <groupId>com.yewuzhongtai</groupId>
    <artifactId>yewuzhongtai-client-starter</artifactId>
    <version>1.0.0-SNAPSHOT</version>
</dependency>
```

### 1.2 最小配置
```yaml
ywt:
  sys-code: crm
  gateway-url: http://ywt-gateway:8080
```

## 二、核心能力

### 2.1 操作日志自动上报 — @YwtLog

注解定义：
```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface YwtLog {
    String title() default "";
    String businessType() default "OTHER";
}
```

使用示例：
```java
@RestController
public class CustomerController {
    @YwtLog(title = "新增客户", businessType = "INSERT")
    @PostMapping("/customer")
    public Result addCustomer(@RequestBody Customer customer) {
        // 业务逻辑
    }
    
    @YwtLog(title = "删除客户", businessType = "DELETE")
    @DeleteMapping("/customer/{id}")
    public Result deleteCustomer(@PathVariable Long id) {
        // 业务逻辑
    }
}
```

AOP 自动采集：方法入参、返回值、耗时、操作用户、IP、URL。异常时自动记录错误信息。异步上报不阻塞业务。

OperLogDTO 字段：`title`, `operName`, `operUrl`, `requestMethod`, `operIp`, `operParam`, `jsonResult`, `status`, `errorMsg`, `costTime`, `sysCode`, `businessType`。

### 2.2 用户上下文 — UserContext
```java
Long userId = UserContext.getCurrentUserId();
String username = UserContext.getCurrentUsername();
String clientIp = UserContext.getClientIp();
```

从 Gateway 透传的 `X-User-Id` / `X-Username` headers 中获取。

### 2.3 Token 自动续期 — TokenHolder + YwtRestTemplateBuilder
- 外部系统通过 SDK 的 RestTemplate 调中台 API 时，自动注入 Authorization header
- 遇 401 自动调用 `/auth/refresh` 刷新 Token 并重试
- 并发刷新保护（ReentrantLock）

使用方式：
```java
// 方式一：注入 RestTemplate（自动带 Token）
@Autowired
private RestTemplate restTemplate;

// 方式二：手动调用
YwtRestTemplateBuilder.executeWithRefresh(restTemplate, props, 
    url, HttpMethod.GET, null, Result.class);
```

手动设置 Token：
```java
TokenHolder.setTokens(accessToken, refreshToken);
```

### 2.4 权限查询 — PermissionClient
```java
@Autowired
private PermissionClient permissionClient;

List<String> permissions = permissionClient.getCurrentUserPermissions();
// 返回当前用户的权限标识列表，如 ["system:user:list", "system:user:add"]
```

### 2.5 登录日志上报 — LogClient
```java
@Autowired
private LogClient logClient;

LoginLogDTO dto = new LoginLogDTO();
dto.setUsername(username);
dto.setIpaddr(ip);
dto.setStatus(0);
logClient.recordLogin(dto);
```

LoginLogDTO 字段：`username`, `ipaddr`, `loginLocation`, `browser`, `os`, `status`, `msg`, `sysCode`。

### 2.6 版本兼容校验
启动时自动调用 `GET /api/registry/version` 校验 SDK 版本与中台兼容性。
不兼容时打印 WARN 日志（不阻止启动）。

## 三、配置参考

### YwtClientProperties
| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `ywt.sys-code` | String | unknown | 系统标识，与注册时一致 |
| `ywt.gateway-url` | String | http://ywt-gateway:8080 | 中台网关地址 |
| `ywt.connect-timeout` | int | 2000 | 连接超时 ms |
| `ywt.read-timeout` | int | 10000 | 读取超时 ms |

## 四、非 Spring Boot 项目接入

如果不使用 Spring Boot，可以：
1. 直接通过 HTTP 调中台 API（JWT 认证）
2. 手动调用 `/auth/login` → `/auth/refresh` 管理 Token
3. 直接调用 `/system/log/oper` 上报操作日志

## 五、API 对照表

| SDK 能力 | 对应 API |
|----------|---------|
| `@YwtLog` 注解 | `POST /system/log/oper` |
| PermissionClient | `GET /system/user/permissions` |
| LogClient.recordLogin | `POST /system/log/login` |
| TokenHolder | `/auth/login` + `/auth/refresh` |
