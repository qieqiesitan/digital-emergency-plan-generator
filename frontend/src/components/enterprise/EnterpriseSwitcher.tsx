import { Select } from "antd";
import { useCurrentEnterprise } from "@/contexts/EnterpriseContext";

export function EnterpriseSwitcher() {
  const { enterprises, currentEnterpriseId, setCurrentEnterprise, isLoading } = useCurrentEnterprise();

  if (isLoading) {
    return <Select style={{ width: 200 }} loading placeholder="加载中..." />;
  }

  return (
    <Select
      style={{ width: 220 }}
      value={currentEnterpriseId}
      onChange={setCurrentEnterprise}
      options={enterprises.map((e) => ({ value: e.id, label: e.name }))}
      placeholder="选择企业"
      notFoundContent="暂无企业，请先创建"
    />
  );
}
