/**
 * `SimpleList`：antd v6 弃用 `List` 之后的替代实现。
 *
 * 为什么是"移植"而不是"重写"：`List` 在 8 个文件 13 处被使用（看板「最近编辑」与
 * 企业切换弹窗、楼层抽屉、风险告知卡预览、AI 风险事件建议弹窗、重大危险源依据面板、
 * 迁移向导、四色图导入弹窗、章节个性化指令面板），逐处手写列表会产生 8 套不一致的
 * 间距。这里按 antd `List` 的 DOM 结构与 `antd/es/list/style/index.js` 的度量做等价
 * 移植（样式在 `@/styles/simple-list.css`），调用方只需把
 * `import { List } from "antd"` 换成 `import List from "@/components/common/SimpleList"`。
 *
 * 与 antd 的差异（有意为之）：
 *  - `actions` 里的 `null`/`undefined`/`false` 占位会被过滤，不渲染幽灵空 `<li>`；
 *  - 不支持分页、栅格（`grid`）、虚拟滚动、`loadMore`、`itemLayout="vertical"`、
 *    `rowKey`（本仓库 13 处均未用到，若将来需要请改用 antd `Table` 或自建）。
 */
import type { CSSProperties, ReactElement, ReactNode } from "react";
import { Fragment } from "react";
import { Empty, Spin } from "antd";
import "@/styles/simple-list.css";

export interface SimpleItemMetaProps {
  title?: ReactNode;
  description?: ReactNode;
  avatar?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

/** 等价于 antd 的 `List.Item.Meta`：avatar + 内容（h4 标题 + 描述）。 */
function SimpleItemMeta({ title, description, avatar, className, style }: SimpleItemMetaProps) {
  return (
    <div className={className ? `simple-list__meta ${className}` : "simple-list__meta"} style={style}>
      {avatar ? <div className="simple-list__meta-avatar">{avatar}</div> : null}
      {title || description ? (
        <div className="simple-list__meta-content">
          {title ? <h4 className="simple-list__meta-title">{title}</h4> : null}
          {description ? <div className="simple-list__meta-desc">{description}</div> : null}
        </div>
      ) : null}
    </div>
  );
}

export interface SimpleListItemProps {
  children?: ReactNode;
  extra?: ReactNode;
  actions?: ReactNode[];
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
}

/** 等价于 antd 的 `List.Item`：children + actions + extra 三个 flex 子项。 */
function SimpleListItem({ children, extra, actions, style, className, onClick }: SimpleListItemProps) {
  // 调用方会用 `cond ? <Button/> : null` 占位（如楼层抽屉的「设为默认」），
  // 先滤掉空位，避免渲染出幽灵空 <li> 影响右侧动作区间距。
  const realActions = (actions ?? []).filter((a) => a !== null && a !== undefined && a !== false);
  return (
    <li className={className ? `simple-list__item ${className}` : "simple-list__item"} style={style} onClick={onClick}>
      {children}
      {realActions.length > 0 ? (
        <ul className="simple-list__actions">
          {realActions.map((action, i) => (
            <li key={i}>
              {action}
              {i !== realActions.length - 1 ? <em className="simple-list__action-split" /> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {extra}
    </li>
  );
}

export interface SimpleListProps<T> {
  dataSource?: T[] | null;
  renderItem?: (item: T, index: number) => ReactNode;
  size?: "small" | "default" | "large";
  header?: ReactNode;
  footer?: ReactNode;
  bordered?: boolean;
  split?: boolean;
  loading?: boolean;
  locale?: { emptyText?: ReactNode };
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}

function SimpleListBase<T>({
  dataSource,
  renderItem,
  size = "default",
  header,
  footer,
  bordered = false,
  split = true,
  loading = false,
  locale,
  className,
  style,
  children,
}: SimpleListProps<T>) {
  const items = dataSource ?? [];
  const classes = [
    "simple-list",
    size === "small" ? "simple-list--small" : "",
    size === "large" ? "simple-list--large" : "",
    split ? "simple-list--split" : "",
    bordered ? "simple-list--bordered" : "",
    footer ? "simple-list--has-footer" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  let content: ReactNode;
  if (items.length > 0) {
    content = (
      <ul className="simple-list__items">
        {items.map((item, index) => (
          // 与 antd 一致：renderItem 的返回值（`List.Item`）本身就是 <li>，
          // 这里只用 Fragment 挂 key，不额外包一层 DOM。
          <Fragment key={index}>{renderItem?.(item, index)}</Fragment>
        ))}
      </ul>
    );
  } else if (loading) {
    content = <div className="simple-list__placeholder" />;
  } else {
    // antd 的空态默认为 `<Empty image={PRESENTED_IMAGE_SIMPLE} />`（见 defaultRenderEmpty）
    content = (
      <div className="simple-list__empty-text">
        {locale?.emptyText ?? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      </div>
    );
  }

  return (
    <div className={classes} style={style}>
      {header ? <div className="simple-list__header">{header}</div> : null}
      {loading ? <Spin>{content}</Spin> : content}
      {children}
      {footer ? <div className="simple-list__footer">{footer}</div> : null}
    </div>
  );
}

type SimpleListItemComponent = typeof SimpleListItem & { Meta: typeof SimpleItemMeta };

export type SimpleListComponent = {
  <T>(props: SimpleListProps<T>): ReactElement;
  Item: SimpleListItemComponent;
};

const SimpleList = Object.assign(SimpleListBase, {
  Item: Object.assign(SimpleListItem, { Meta: SimpleItemMeta }),
}) as SimpleListComponent;

export default SimpleList;
