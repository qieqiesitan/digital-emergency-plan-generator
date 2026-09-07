import { useNavigate } from "react-router-dom";
import { Button, Result } from "antd";

/** 未匹配路径的明确 404 页：替代静默跳回工作台。 */
export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="访问的页面不存在或已被移动，请检查链接是否正确。"
      extra={
        <Button type="primary" onClick={() => navigate("/dashboard", { replace: true })}>
          返回工作台
        </Button>
      }
    />
  );
}
