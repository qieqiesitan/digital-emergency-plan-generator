import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Input from "@/mobile/components/ui/Input";
import SelectSheet from "@/mobile/components/ui/SelectSheet";

const INDUSTRY_OPTIONS = [
  "工贸", "危化", "矿山", "建筑", "交通",
  "电力", "水利", "农业", "商贸", "教育",
  "医疗", "餐饮", "物业", "其他",
];

export interface EnterpriseFormData {
  name: string;
  industry: string;
  business_scope: string;
  employee_count: number | null;
  address: string;
  province?: string;
  city?: string;
  district?: string;
}

interface EnterpriseFormProps {
  initialValues?: Partial<EnterpriseFormData>;
  onSubmit: (data: EnterpriseFormData) => Promise<void>;
  submitLabel?: string;
}

export default function EnterpriseForm({
  initialValues,
  onSubmit,
  submitLabel = "保存",
}: EnterpriseFormProps) {
  const [values, setValues] = useState<EnterpriseFormData>({
    name: initialValues?.name ?? "",
    industry: initialValues?.industry ?? "",
    business_scope: initialValues?.business_scope ?? "",
    employee_count: initialValues?.employee_count ?? null,
    address: initialValues?.address ?? "",
    province: initialValues?.province ?? "",
    city: initialValues?.city ?? "",
    district: initialValues?.district ?? "",
  });
  const [errors, setErrors] = useState<Partial<Record<keyof EnterpriseFormData, string>>>({});
  const [submitting, setSubmitting] = useState(false);

  const set = (key: keyof EnterpriseFormData, val: string | number | null) => {
    setValues(prev => ({ ...prev, [key]: val }));
    if (errors[key]) setErrors(prev => ({ ...prev, [key]: undefined }));
  };

  const validate = (): boolean => {
    const e: Partial<Record<keyof EnterpriseFormData, string>> = {};
    if (!values.name.trim()) e.name = "企业名称不能为空";
    else if (values.name.length > 100) e.name = "企业名称最多100个字符";
    if (!values.industry) e.industry = "请选择行业分类";
    if (values.employee_count !== null && values.employee_count < 0) {
      e.employee_count = "员工人数不能为负数";
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    try {
      await onSubmit(values);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-lg">
      {/* 基本信息 */}
      <div>
        <p className="text-h2 mb-md">基本信息</p>
        <div className="bg-white rounded-md shadow-card p-md space-y-md">
          <Input
            label="企业名称"
            required
            value={values.name}
            onChange={(v) => set("name", v)}
            placeholder="请输入企业名称"
            error={errors.name}
          />
          <SelectSheet
            label="行业分类"
            required
            value={values.industry}
            options={INDUSTRY_OPTIONS.map(o => ({ label: o, value: o }))}
            onChange={(v) => set("industry", v)}
            placeholder="选择行业分类"
          />
          <Input
            label="经营范围"
            value={values.business_scope}
            onChange={(v) => set("business_scope", v)}
            placeholder="请输入经营范围"
            multiline
          />
          <Input
            label="员工人数"
            type="number"
            value={values.employee_count !== null ? String(values.employee_count) : ""}
            onChange={(v) => {
              const n = v === "" ? null : parseInt(v, 10);
              set("employee_count", isNaN(n as number) ? null : n);
            }}
            placeholder="0"
            suffix="人"
            error={errors.employee_count}
          />
        </div>
      </div>

      {/* 地址信息 */}
      <div>
        <p className="text-h2 mb-md">地址信息</p>
        <div className="bg-white rounded-md shadow-card p-md space-y-md">
          <Input
            label="详细地址"
            value={values.address}
            onChange={(v) => set("address", v)}
            placeholder="请输入详细地址"
          />
        </div>
      </div>

      {/* 提交按钮 */}
      <motion.button
        className="w-full h-12 bg-primary-600 text-white rounded-md font-semibold text-body disabled:opacity-50"
        whileTap={{ scale: 0.98 }}
        onClick={handleSubmit}
        disabled={submitting}
      >
        {submitting ? "保存中…" : submitLabel}
      </motion.button>
    </div>
  );
}
