import { Modal } from "antd";
import { ExclamationCircleOutlined } from "@ant-design/icons";

export function useConfirmDelete() {
  return (title: string, onOk: () => void) => {
    Modal.confirm({
      title: "确认删除",
      icon: <ExclamationCircleOutlined />,
      content: `确定要删除"${title}"吗？此操作不可撤销。`,
      okText: "确认删除",
      okType: "danger",
      cancelText: "取消",
      onOk,
    });
  };
}
