import { useEffect, useState } from "react";
import dayjs from "dayjs";
import QRCode from "qrcode";
import { QrcodeOutlined } from "@ant-design/icons";
import type { CardData } from "@/types/riskNoticeCard";

/** 空正文兜底文案（与后端 docx 渲染一致，预览页等复用）。 */
export const EMPTY_TEXT = "暂无，请先完善风险评估数据";

/** 卡片样式：.rnc-* 前缀避免与全局/antd 样式冲突。 */
const RNC_CSS = `
.rnc-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  color: #333;
  font-size: 13px;
  line-height: 1.6;
}
.rnc-header {
  position: relative;
  padding: 18px 76px 0 20px;
  text-align: center;
}
.rnc-enterprise {
  color: #666;
  font-size: 12px;
}
.rnc-title {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 2px;
  margin: 4px 0 12px;
}
.rnc-rule {
  height: 3px;
}
.rnc-qr {
  position: absolute;
  right: 14px;
  text-align: center;
  top: 14px;
}
.rnc-qr-box {
  align-items: center;
  background: #fff;
  border: 1px dashed #bfbfbf;
  border-radius: 4px;
  color: #8c8c8c;
  display: flex;
  font-size: 24px;
  height: 44px;
  justify-content: center;
  width: 44px;
}
.rnc-qr-text {
  color: #999;
  font-size: 10px;
  margin-top: 2px;
}
.rnc-qr-img {
  display: block;
  height: 56px;
  width: 56px;
}
.rnc-body {
  display: flex;
  align-items: stretch;
}
.rnc-left {
  background: #fbfbfb;
  border-right: 1px solid #eee;
  width: 40%;
}
.rnc-right {
  width: 60%;
}
.rnc-level-band {
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 6px;
  padding: 8px 0;
  text-align: center;
}
.rnc-table {
  background: #fff;
  border-collapse: collapse;
  width: 100%;
}
.rnc-table td {
  border: 1px solid #eee;
  font-size: 12.5px;
  padding: 6px 8px;
}
.rnc-table td:first-child {
  background: #f2f2f2;
  color: #333;
  font-weight: 700;
  text-align: center;
  white-space: nowrap;
  width: 62px;
}
.rnc-table td:last-child {
  background: #fff;
  font-weight: 700;
}
.rnc-signs-title {
  background: #434343;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 8px;
  padding: 6px 0;
  text-align: center;
}
.rnc-signs {
  background: #fff;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  padding: 12px;
}
.rnc-sign {
  text-align: center;
  width: 64px;
}
.rnc-sign img {
  display: block;
  height: 56px;
  margin: 0 auto;
  width: 56px;
}
.rnc-sign-name {
  color: #333;
  font-size: 11px;
  line-height: 1.3;
  margin-top: 2px;
}
.rnc-block {
  border-bottom: 1px solid #f0f0f0;
}
.rnc-block:last-child {
  border-bottom: none;
}
.rnc-block-title {
  background: #434343;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 2px;
  padding: 6px 12px;
}
.rnc-block-title::before {
  background: #ff4d4f;
  border-radius: 50%;
  content: "";
  display: inline-block;
  height: 6px;
  margin-right: 8px;
  vertical-align: 2px;
  width: 6px;
}
.rnc-block-body {
  background: #fff;
  font-size: 13px;
  min-height: 44px;
  padding: 10px 12px;
}
.rnc-empty {
  color: #bfbfbf;
}
.rnc-footer {
  border-top: 1px solid #f0f0f0;
  color: #666;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 8px;
  justify-content: center;
  padding: 12px;
  text-align: center;
}
/* 窄屏（手机扫码主场景）：左右栏纵向堆叠，安全标志缩至 48px */
@media (max-width: 520px) {
  .rnc-header {
    padding: 14px 14px 0;
  }
  .rnc-qr {
    margin: 0 auto 10px;
    position: static;
  }
  .rnc-qr-box {
    margin: 0 auto;
  }
  .rnc-title {
    font-size: 16px;
    letter-spacing: 1px;
  }
  .rnc-body {
    flex-direction: column;
  }
  .rnc-left,
  .rnc-right {
    width: 100%;
  }
  .rnc-left {
    border-bottom: 1px solid #eee;
    border-right: none;
  }
  .rnc-sign {
    width: 56px;
  }
  .rnc-sign img {
    height: 48px;
    width: 48px;
  }
  .rnc-table td {
    padding: 5px 6px;
  }
  .rnc-table td:first-child {
    width: 52px;
  }
  .rnc-block-title {
    letter-spacing: 1px;
    padding: 6px 10px;
  }
  .rnc-block-body {
    padding: 8px 10px;
  }
}
`;

type TableField =
  | "name"
  | "code"
  | "level"
  | "responsible_unit"
  | "responsible_person"
  | "contact_phone";

const KEY_VALUE_ROWS: ReadonlyArray<readonly [label: string, key: TableField]> = [
  ["风险点名称", "name"],
  ["风险点编号", "code"],
  ["风险等级", "level"],
  ["责任单位", "responsible_unit"],
  ["责任人", "responsible_person"],
  ["联系电话", "contact_phone"],
];

/** 编制日期本地化：ISO 时间转 YYYY年M月D日，解析失败回退原串前 10 位。 */
function formatIssueDate(raw: string): string {
  const parsed = dayjs(raw);
  return parsed.isValid() ? parsed.format("YYYY年M月D日") : raw.slice(0, 10);
}

interface InfoBlockProps {
  title: string;
  body: string;
}

/** 右栏信息块：深色标题条（红点）+ 白底正文，空内容兜底。 */
function InfoBlock({ title, body }: InfoBlockProps) {
  const text = body.trim();
  return (
    <div className="rnc-block">
      <div className="rnc-block-title">{title}</div>
      <div className="rnc-block-body">
        {text ? (
          text.split("\n").map((line, index) => <div key={index}>{line}</div>)
        ) : (
          <span className="rnc-empty">{EMPTY_TEXT}</span>
        )}
      </div>
    </div>
  );
}

interface RiskNoticeCardProps {
  card: CardData;
}

/** 风险告知卡（v5 版式）：头部 + 左右分栏 + 页脚，与 Word 导出布局一致。 */
export default function RiskNoticeCard({ card }: RiskNoticeCardProps) {
  const accidentText = card.accident_types.length
    ? `${card.accident_types.join("、")}（GB 6441 事故类别）`
    : "";
  const versionText = card.snapshot ? `V1.${card.snapshot.version}` : "V1.0";
  const [qrDataUrl, setQrDataUrl] = useState("");

  useEffect(() => {
    let cancelled = false;
    const fullUrl = `${window.location.origin}${card.public_url}`;
    QRCode.toDataURL(fullUrl, { width: 112, margin: 1 })
      .then((url) => {
        if (!cancelled) setQrDataUrl(url);
      })
      .catch(() => {
        if (!cancelled) setQrDataUrl("");
      });
    return () => {
      cancelled = true;
    };
  }, [card.public_url]);

  return (
    <div className="rnc-card">
      <style>{RNC_CSS}</style>
      <div className="rnc-header">
        <div className="rnc-qr">
          {qrDataUrl ? (
            <img className="rnc-qr-img" src={qrDataUrl} alt="扫码查看" />
          ) : (
            <div className="rnc-qr-box">
              <QrcodeOutlined />
            </div>
          )}
          <div className="rnc-qr-text">扫码查看</div>
        </div>
        <div className="rnc-enterprise">{card.enterprise_name}</div>
        <div className="rnc-title">{card.name}安全风险告知卡</div>
      </div>
      <div className="rnc-rule" style={{ background: card.level_color }} />

      <div className="rnc-body">
        <div className="rnc-left">
          <div className="rnc-level-band" style={{ background: card.level_color }}>
            现有风险：{card.level}
            {card.inherent_risk_level ? `（固有 ${card.inherent_risk_level}）` : ""}
          </div>
          <table className="rnc-table">
            <tbody>
              {KEY_VALUE_ROWS.map(([label, key]) => (
                <tr key={key}>
                  <td>{label}</td>
                  <td>{card[key]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="rnc-signs-title">安全标志</div>
          <div className="rnc-signs">
            {card.signs.length ? (
              card.signs.map((sign) => (
                <div className="rnc-sign" key={sign.svg_name}>
                  <img src={`/signs/${sign.svg_name}.svg`} alt={sign.name} />
                  <div className="rnc-sign-name">{sign.name}</div>
                </div>
              ))
            ) : (
              <span className="rnc-empty">{EMPTY_TEXT}</span>
            )}
          </div>
        </div>

        <div className="rnc-right">
          <InfoBlock title="主要危险因素描述" body={card.hazard_description} />
          <InfoBlock title="主要事故类型" body={accidentText} />
          <InfoBlock
            title="主要风险控制措施"
            body={card.control_measures.join("\n")}
          />
          <InfoBlock
            title="应急处置措施"
            body={card.emergency_measures.join("\n")}
          />
        </div>
      </div>

      <div className="rnc-footer">
        <span>签发单位：{card.enterprise_name}</span>
        <span>编制日期：{formatIssueDate(card.generated_at)}</span>
        <span>版本：{versionText}</span>
      </div>
    </div>
  );
}
