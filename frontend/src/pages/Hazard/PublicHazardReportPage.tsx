import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Form,
  Input,
  Result,
  Space,
  Typography,
  Upload,
} from "antd";
import type { UploadFile } from "antd";
import { CameraOutlined, SendOutlined } from "@ant-design/icons";
import axios from "axios";
import { submitPublicHazardReport } from "@/services/hazardService";

const { Paragraph } = Typography;

const MAX_PHOTOS = 3;
const MAX_PHOTO_BYTES = 2 * 1024 * 1024;

/** 一次性 nonce：uuid 优先，兜底时间戳+随机串（§8 幂等，后端 5 分钟防重）。 */
function generateNonce(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `n-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

interface ReportFormValues {
  description: string;
  location?: string;
  nonce?: string;
}

/** 扫码公开上报页（/h/report/:token，免登录，§8）。 */
export default function PublicHazardReportPage() {
  const { token = "" } = useParams<{ token: string }>();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm<ReportFormValues>();
  const [nonce] = useState<string>(generateNonce);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [duplicate, setDuplicate] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [photoUrls, setPhotoUrls] = useState<string[]>([]);

  const handleBeforeUpload = (file: File) => {
    if (fileList.length >= MAX_PHOTOS) {
      message.warning(`最多上传 ${MAX_PHOTOS} 张照片`);
      return Upload.LIST_IGNORE;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      message.warning("单张照片不能超过 2MB");
      return Upload.LIST_IGNORE;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const url = typeof reader.result === "string" ? reader.result : "";
      if (!url) return;
      setPhotoUrls(prev => [...prev, url]);
      setFileList(prev => [
        ...prev,
        { uid: url, name: file.name, status: "done", url },
      ]);
    };
    reader.readAsDataURL(file);
    // 免登录页无法使用需鉴权的 /api/v1/upload：转为 data URL 直传（取舍，见报告）
    return false;
  };

  const handleRemove = (file: UploadFile) => {
    setPhotoUrls(prev => prev.filter(u => u !== file.uid));
    setFileList(prev => prev.filter(f => f.uid !== file.uid));
  };

  const handleSubmit = async (values: ReportFormValues) => {
    setSubmitting(true);
    try {
      await submitPublicHazardReport(token, {
        description: values.description.trim(),
        location: values.location?.trim() || undefined,
        photo_urls: photoUrls.length ? photoUrls : undefined,
        nonce,
      });
      setSubmitted(true);
    } catch (e) {
      if (axios.isAxiosError(e)) {
        const status = e.response?.status;
        if (status === 404) {
          setInvalid(true);
        } else if (status === 409) {
          setDuplicate(true);
        } else {
          message.error(extractDetail(e) || "提交失败，请稍后重试");
        }
      } else {
        message.error("提交失败，请稍后重试");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (invalid) {
    return (
      <Result
        status="404"
        title="链接已失效"
        subTitle="该上报链接已失效，请联系企业获取最新二维码"
      />
    );
  }

  if (duplicate) {
    return (
      <Result
        status="warning"
        title="请勿重复提交"
        subTitle="该表单已提交过，请勿重复提交；如需上报其他隐患请刷新页面"
        extra={
          <Button type="primary" onClick={() => window.location.reload()}>
            刷新页面
          </Button>
        }
      />
    );
  }

  if (submitted) {
    return (
      <Result
        status="success"
        title="已提交，待企业管理员确认"
        subTitle="感谢反馈！企业管理员将尽快核实处理该隐患。"
      />
    );
  }

  return (
    <div style={{ margin: "0 auto", maxWidth: 560, padding: "32px 16px" }}>
      <Alert
        type="info"
        showIcon
        message="免登录公开上报"
        description="本页面仅用于隐患上报，不展示企业内部数据；提交后由企业管理员确认处理。"
        style={{ marginBottom: 20 }}
      />
      <Card title="隐患上报">
        <Form<ReportFormValues>
          form={form}
          layout="vertical"
          onFinish={values => void handleSubmit(values)}
          requiredMark="optional"
        >
          <Form.Item name="nonce" hidden initialValue={nonce}>
            <Input />
          </Form.Item>
          <Form.Item
            name="description"
            label="隐患描述"
            rules={[{ required: true, message: "请填写隐患描述" }]}
          >
            <Input.TextArea
              rows={4}
              placeholder="请描述隐患情况（如：3 号车间配电箱门破损、线缆裸露）"
              maxLength={2000}
              showCount
            />
          </Form.Item>
          <Form.Item
            name="location"
            label="位置"
            extra="企业通用二维码上报时位置必填；风险点二维码可留空。"
          >
            <Input placeholder="如：3 号车间东侧" maxLength={500} />
          </Form.Item>
          <Form.Item label="照片（可选，最多 3 张，单张 ≤2MB）">
            <Upload
              listType="picture-card"
              fileList={fileList}
              beforeUpload={handleBeforeUpload}
              onRemove={handleRemove}
              accept="image/*"
              maxCount={MAX_PHOTOS}
            >
              {fileList.length < MAX_PHOTOS ? (
                <div>
                  <CameraOutlined style={{ fontSize: 20 }} />
                  <div style={{ marginTop: 4, fontSize: 12 }}>上传</div>
                </div>
              ) : null}
            </Upload>
          </Form.Item>
          <Space direction="vertical" style={{ width: "100%" }}>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SendOutlined />}
              loading={submitting}
              block
            >
              提交上报
            </Button>
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 0, textAlign: "center" }}>
              提交后该表单不可重复提交（防重校验），请确认内容后再提交。
            </Paragraph>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
