# 企业基本信息补充开发计划

## 当前状态

Enterprise 模型现有 10 个字段：name, address, industry, business_scope, employee_count, building_overview, org_structure, surrounding_info, floor_plan_url, gis_lat/lng

## 需补充字段（18个）

### 法定基本信息
- credit_code（统一社会信用代码）
- legal_representative（法定代表人）
- economic_type（经济类型）
- established_date（成立日期）
- registered_capital（注册资本/万元）

### 联系与位置
- phone（联系电话）
- fax（传真）
- postal_code（邮政编码）
- land_area（占地面积/㎡）
- building_area（建筑面积/㎡）

### 安全管理
- safety_officer（安全负责人）
- safety_officer_phone（安全负责人电话）
- safety_staff_count（安全管理人员数）
- safety_standardization（安全标准化等级）
- fire_approval（消防验收情况）
- last_plan_filing_date（上次备案日期）
- last_plan_filing_authority（上次备案部门）

### 生产信息
- main_products（主要产品）
- annual_capacity（年产能）
- hazardous_chemicals（危化品信息）
- special_equipment（特种设备）

## 实施步骤
1. 数据库模型新增字段
2. Pydantic Schema 同步
3. 前端创建/编辑页表单分组
4. 前端详情页展示扩展
5. 提示词上下文引入新字段
6. 数据库迁移 + 验证
