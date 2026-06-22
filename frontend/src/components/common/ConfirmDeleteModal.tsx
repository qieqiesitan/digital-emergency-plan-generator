import { Modal } from "antd";
import { ExclamationCircleOutlined } from "@ant-design/icons";

interface ConfirmDeleteModalProps {
  open: boolean;
  title: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ConfirmDeleteModal({ open, title, onConfirm, onCancel, loading }: ConfirmDeleteModalProps) {
  return (
    <Modal
      open={open}
      title={
        <span>
          <ExclamationCircleOutlined style={{ color: "#ff4d4f", marginRight: 8 }} />
          确认删除
        </span>
      }
      onOk={onConfirm}
      onCancel={onCancel}
      okText="确认删除"
      okType="danger"
      cancelText="取消"
      confirmLoading={loading}
    >
      <p>确定要删除「{title}」吗？此操作不可撤销。</p>
    </Modal>
  );
}
