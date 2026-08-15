import { useNavigate, useParams } from "react-router-dom";
import { Button, Empty } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { PageHeader } from "@/components/common/PageHeader";

interface Props {
  title: string;
  /** 返回目标路径；缺省返回上一页 */
  backTo?: string;
  hint?: string;
}

/** 隐患模块路由占位页：任务 14-16 逐个实现后替换，本页仅保证入口可导航。 */
export default function HazardPlaceholderPage({ title, backTo, hint }: Props) {
  const navigate = useNavigate();
  const { id } = useParams<{ id?: string }>();
  // 企业内页面缺省返回「企业详情 → 隐患排查治理 Tab」；公开页缺省返回首页
  const target = backTo ?? (id ? `/enterprises/${id}?tab=hazard-inspection` : "/");
  return (
    <div>
      <PageHeader
        title={title}
        onBack={() => navigate(target)}
      />
      <Empty
        style={{ marginTop: 64 }}
        description={hint || "该页面在后续迭代中实现（隐患任务 14-16），敬请期待"}
      >
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(target)}>
          返回
        </Button>
      </Empty>
    </div>
  );
}
