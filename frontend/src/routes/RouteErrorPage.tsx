import { isRouteErrorResponse, useNavigate, useRouteError } from "react-router-dom";
import { Button, Result } from "antd";

/** 路由级错误兜底：运行时异常不再整屏白屏，未匹配路径有明确提示。 */
export default function RouteErrorPage() {
  const error = useRouteError();
  const navigate = useNavigate();
  const is404 = isRouteErrorResponse(error) && error.status === 404;

  return (
    <Result
      status="error"
      title={is404 ? "页面不存在" : "页面出错了"}
      subTitle={
        is404
          ? "访问的页面不存在或已被移动，请检查链接或返回工作台。"
          : "页面运行时出现异常，请刷新重试，或返回工作台。"
      }
      extra={[
        <Button key="reload" onClick={() => window.location.reload()}>
          刷新页面
        </Button>,
        <Button key="home" type="primary" onClick={() => navigate("/dashboard", { replace: true })}>
          返回工作台
        </Button>,
      ]}
    />
  );
}
