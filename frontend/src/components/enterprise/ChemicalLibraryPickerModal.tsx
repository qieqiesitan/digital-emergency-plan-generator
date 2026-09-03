import { useEffect, useState } from "react";
import { Button, Empty, Input, Modal, Table } from "antd";
import { listLibrary } from "@/services/chemicalLibraryService";
import type { ChemicalLibraryItem } from "@/types/chemicalLibrary";

interface Props {
  open: boolean;
  onSelect: (item: ChemicalLibraryItem) => void;
  onManual: () => void;
  onClose: () => void;
}

export default function ChemicalLibraryPickerModal({ open, onSelect, onManual, onClose }: Props) {
  const [keyword, setKeyword] = useState("");
  const [items, setItems] = useState<ChemicalLibraryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const fetch = async (kw: string, pg: number) => {
    setLoading(true);
    try {
      const res = await listLibrary(kw, { page: pg, page_size: PAGE_SIZE });
      setItems(res.data.items || []);
      setTotal(res.data.total || 0);
      setPage(pg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      setKeyword("");
      fetch("", 1);
    }
  }, [open]);

  const columns = [
    { title: "化学品名称", dataIndex: "name", key: "name", width: 200 },
    { title: "CAS号", dataIndex: "cas_no", key: "cas_no", width: 130, render: (v: string | null) => v || "-" },
    { title: "UN号", dataIndex: "un_no", key: "un_no", width: 90, render: (v: string | null) => v || "-" },
    { title: "物理状态", dataIndex: "physical_state", key: "physical_state", width: 100, render: (v: string | null) => v || "-" },
    { title: "闪点", dataIndex: "flash_point", key: "flash_point", width: 100, render: (v: string | null) => v || "-" },
  ];

  return (
    <Modal
      title="从化学品库选择"
      open={open}
      onCancel={onClose}
      footer={null}
      width={820}
      destroyOnHidden
    >
      <Input.Search
        placeholder="按名称 / CAS号 / UN号搜索"
        allowClear
        enterButton="搜索"
        onSearch={(v) => fetch(v.trim(), 1)}
        style={{ marginBottom: 12 }}
      />
      <Table
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total,
          onChange: (p) => fetch(keyword, p),
          showTotal: (t) => `共 ${t} 条`,
        }}
        onRow={(record) => ({
          onClick: () => onSelect(record),
          style: { cursor: "pointer" },
        })}
        locale={{
          emptyText: (
            <Empty
              description="化学品库暂无匹配条目"
            >
              <Button type="link" onClick={onManual}>未找到？手动填写</Button>
            </Empty>
          ),
        }}
      />
    </Modal>
  );
}
