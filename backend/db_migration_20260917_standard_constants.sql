-- 20260917 GB 18218-2018《危险化学品重大危险源辨识》常量表与种子数据
-- 本文件由 scripts/gen_major_hazard_seed_sql.py 生成，请勿手工编辑。
-- 数据来源：docs/标准数据-GB18218-2018/（标准正本 PDF 抽取，CAS 校验位已逐条验证）。
-- id 使用 uuid5(NAMESPACE_URL, 'major-hazard/GB18218-2018/<表>/<自然键>')，
-- 每条插入均按主键冲突跳过，保证幂等可重放。

CREATE TABLE IF NOT EXISTS critical_quantities (
    id UUID PRIMARY KEY,
    standard VARCHAR(40) NOT NULL,
    table_no VARCHAR(4) NOT NULL,
    chemical_name VARCHAR(500) NOT NULL,
    alias VARCHAR(500),
    cas_no VARCHAR(120),
    category VARCHAR(80),
    symbol VARCHAR(20),
    critical_t NUMERIC(18, 6),
    critical_note VARCHAR(80),
    source_page INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cq_table1_name
    ON critical_quantities (standard, chemical_name) WHERE table_no = '1';
CREATE UNIQUE INDEX IF NOT EXISTS uq_cq_table2_symbol
    ON critical_quantities (standard, symbol) WHERE table_no = '2';
CREATE INDEX IF NOT EXISTS ix_cq_cas ON critical_quantities (cas_no);

CREATE TABLE IF NOT EXISTS hazard_beta_factors (
    id UUID PRIMARY KEY,
    standard VARCHAR(40) NOT NULL,
    source_table VARCHAR(4) NOT NULL,
    chemical_name VARCHAR(200),
    category VARCHAR(80),
    symbol VARCHAR(20),
    beta NUMERIC(6, 3) NOT NULL,
    source_page INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_hbf_name ON hazard_beta_factors (standard, chemical_name);
CREATE INDEX IF NOT EXISTS ix_hbf_symbol ON hazard_beta_factors (standard, symbol);

CREATE TABLE IF NOT EXISTS exposure_alpha_factors (
    id UUID PRIMARY KEY,
    standard VARCHAR(40) NOT NULL,
    label VARCHAR(40) NOT NULL,
    population_min INTEGER NOT NULL,
    population_max INTEGER,
    alpha NUMERIC(4, 2) NOT NULL,
    source_page INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_eaf_label
    ON exposure_alpha_factors (standard, label);

CREATE TABLE IF NOT EXISTS major_hazard_levels (
    id UUID PRIMARY KEY,
    standard VARCHAR(40) NOT NULL,
    level_name VARCHAR(20) NOT NULL,
    r_expression VARCHAR(60) NOT NULL,
    r_min NUMERIC(12, 3),
    r_max NUMERIC(12, 3),
    source_page INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mhl_level
    ON major_hazard_levels (standard, level_name);

INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('f18342ee-b1d3-5a07-8d70-a1b8136961e3', 'GB18218-2018', '1', '氨', '液氨;氨气', '7664-41-7', 10, NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('ebc30ab3-51d1-59c3-b397-c75fd7d051f2', 'GB18218-2018', '1', '二氟化氧', '一氧化二氟', '7783-41-7', 1, NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('8e1dd6c0-651b-5761-8e14-d8381dd50d49', 'GB18218-2018', '1', '二氧化氮', NULL, '10102-44-0', 1, NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('7bb1824e-b8c5-529e-8e38-4aba200f89d6', 'GB18218-2018', '1', '二氧化硫', '亚硫酸酐', '7446-09-5', 20, NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('d1b1e383-87f8-5de0-b520-88aa0ddeb7cb', 'GB18218-2018', '1', '氟', NULL, '7782-41-4', 1, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c95ed15b-a8d3-5228-a9ee-ac016a619397', 'GB18218-2018', '1', '碳酰氯', '光气', '75-44-5', 0.3, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('4fd73cee-ace5-50dd-9db3-5eadc84fbc00', 'GB18218-2018', '1', '环氧乙烷', '氧化乙烯', '75-21-8', 10, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('9a751761-c96a-5209-a1cf-1622b22be4ac', 'GB18218-2018', '1', '甲醛(含量>90%)', '蚁醛', '50-00-0', 5, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('6f7f14b7-ed3d-5df7-904c-c54ae0cc186b', 'GB18218-2018', '1', '磷化氢', '磷化三氢;膦', '7803-51-2', 1, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('ad6985c4-aece-5589-b242-ab7f87952533', 'GB18218-2018', '1', '硫化氢', NULL, '7783-06-4', 5, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('b8e6f0f6-368d-53b6-adbd-26ed2af78f1a', 'GB18218-2018', '1', '氯化氢(无水)', NULL, '7647-01-0', 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('960356cf-ddbd-55a3-8f61-344bebad1b10', 'GB18218-2018', '1', '氯', '液氯;氯气', '7782-50-5', 5, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c7490e02-6121-546c-ba96-74707e21eb31', 'GB18218-2018', '1', '煤气(CO,CO和H₂、CH₄的混合物等)', NULL, NULL, 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('937173f1-28c4-5c69-8f10-fd39db6f56c2', 'GB18218-2018', '1', '砷化氢', '砷化三氢、胂', '7784-42-1', 1, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('a2a538e3-a263-587d-b004-0ed5a922c8d7', 'GB18218-2018', '1', '锑化氢', '三氢化锑;锑化三氢;', '7803-52-3', 1, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('ea38a4e9-a3f6-5646-b398-d40224c17dd3', 'GB18218-2018', '1', '硒化氢', NULL, '7783-07-5', 1, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('9ea19c71-bc69-5da6-9bbd-bedf6bfeb523', 'GB18218-2018', '1', '溴甲烷', '甲基溴', '74-83-9', 10, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('98d5b17b-b60c-56da-8bbf-c3559426f851', 'GB18218-2018', '1', '丙酮氰醇', '丙酮合氰化氢;2-羟基异丁腈;氰丙醇', '75-86-5', 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('0e0ff6c7-b133-509a-b214-29fc69dbf73f', 'GB18218-2018', '1', '丙烯醛', '烯丙醛;败脂醛', '107-02-8', 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('ad7d3bf3-77ac-5c80-be7d-5a4a611c0207', 'GB18218-2018', '1', '氟化氢', NULL, '7664-39-3', 1, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('1298dadb-c21c-5df7-b5f0-0876921b29e4', 'GB18218-2018', '1', '1-氯-2,3-环氧丙烷', '环氧氯丙烷(3-氯-1,2-环氧丙烷)', '106-89-8', 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('d5a1d007-7dfc-54f6-9047-e6a18b3926e0', 'GB18218-2018', '1', '3-溴-1,2-环氧丙烷', '环氧溴丙烷;溴甲基环氧乙烷;表溴醇', '3132-64-7', 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('ebdf34b1-69eb-5c64-8874-093d730a9d6c', 'GB18218-2018', '1', '甲苯二异氰酸酯', '二异氰酸甲苯酯;TDI', '26471-62-5', 100, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('6e89bef4-5c0e-529c-861c-5a497488630a', 'GB18218-2018', '1', '一氯化硫', '氯化硫', '10025-67-9', 1, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('24942af3-29f8-5467-87cf-a10cd1b11acb', 'GB18218-2018', '1', '氰化氢', '无水氢氰酸', '74-90-8', 1, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('4e614b40-882c-5f9f-bfff-f67392554632', 'GB18218-2018', '1', '三氧化硫', '硫酸酐', '7446-11-9', 75, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('54af619c-49bb-5996-8871-b634973b2298', 'GB18218-2018', '1', '3-氨基丙烯', '烯丙胺', '107-11-9', 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('13cc3604-cb6e-569e-a1cc-d4ca44096c97', 'GB18218-2018', '1', '溴', '溴素', '7726-95-6', 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c3036d95-c9e3-5150-bb3a-41fa9ebf76e0', 'GB18218-2018', '1', '乙撑亚胺', '吖丙啶;1-氮杂环丙烷;氮丙啶', '151-56-4', 20, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('d00a01bc-bd7e-557f-b964-648f523062a3', 'GB18218-2018', '1', '异氰酸甲酯', '甲基异氰酸酯', '624-83-9', 0.75, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c1538761-bb27-57c1-88b0-7d93b63d94b0', 'GB18218-2018', '1', '叠氮化钡', '叠氮钡', '18810-58-7', 0.5, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('eb34df60-4e49-5d32-b7ef-2e22b28e7b8b', 'GB18218-2018', '1', '叠氮化铅', NULL, '13424-46-9', 0.5, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('06631b20-e609-55bf-8e34-c1f02fc611bb', 'GB18218-2018', '1', '雷汞', '二雷酸汞;雷酸汞', '628-86-4', 0.5, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('63e73960-4445-573c-a4f4-661c14afef80', 'GB18218-2018', '1', '三硝基苯甲醚', '三硝基茴香醚', '28653-16-9', 5, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('dbd595e9-88b3-5a25-b557-ef046d110337', 'GB18218-2018', '1', '2,4,6-三硝基甲苯', '梯恩梯;TNT', '118-96-7', 5, NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('9ba88bf2-3e6e-5df2-be03-7aa48769008a', 'GB18218-2018', '1', '硝化甘油', '硝化丙三醇;甘油三硝酸酯', '55-63-0', 1, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('8ad1ce6d-b8ed-51ca-b268-deda649c8cef', 'GB18218-2018', '1', '硝化纤维素［干的或含水(或乙醇)<25%］', '硝化棉', '9004-70-0', 1, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('eb794ecb-59aa-547c-9104-6d427e423237', 'GB18218-2018', '1', '硝化纤维素(未改型的,或增塑的,含增塑剂<18%)', '硝化棉', '9004-70-0', 1, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c4d0d96a-50b6-5341-b2ae-802dbac7c1dc', 'GB18218-2018', '1', '硝化纤维素(含乙醇≥25%)', '硝化棉', '9004-70-0', 10, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('f4a58d58-5803-5895-8848-4e2a3c8ac1ff', 'GB18218-2018', '1', '硝化纤维素(含氮≤12.6%)', '硝化棉', '9004-70-0', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('ba16d100-fb98-57b2-9552-f8a46a3b305c', 'GB18218-2018', '1', '硝化纤维素(含水≥25%)', '硝化棉', '9004-70-0', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('41099a2b-a262-5e01-86fc-7dc7c1c75a25', 'GB18218-2018', '1', '硝化纤维素溶液(含氮量≤12.6%,含硝化纤维素≤55%)', '硝化棉溶液', '9004-70-0', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('0916609f-34cc-52b3-9cdb-3257fd09e0e8', 'GB18218-2018', '1', '硝酸铵(含可燃物>0.2%,包括以碳计算的任何有机物,但不包括任何其他添加剂)', NULL, '6484-52-2', 5, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('0c77262a-6bce-5a9d-aabe-aeef0366190d', 'GB18218-2018', '1', '硝酸铵(含可燃物≤0.2%)', NULL, '6484-52-2', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('b8d8022a-9ed1-5a77-b383-ab64ac55a148', 'GB18218-2018', '1', '硝酸铵肥料(含可燃物≤0.4%)', NULL, NULL, 200, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('29e0dde6-8c33-5e88-ac6b-bd3b09cc2810', 'GB18218-2018', '1', '硝酸钾', NULL, '7757-79-1', 1000, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('9d1f1697-ace4-598f-a5bc-f19731bb9a2a', 'GB18218-2018', '1', '1,3-丁二烯', '联乙烯', '106-99-0', 5, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('8acc765a-491e-5b65-a8be-3696c5793c3b', 'GB18218-2018', '1', '二甲醚', '甲醚', '115-10-6', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('0a214b4c-b733-582b-ab12-4149952071db', 'GB18218-2018', '1', '甲烷,天然气', NULL, '74-82-8(甲烷)；8006-14-2(天然气)', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('9fb575e4-e46d-5e24-879a-659b62d66e3f', 'GB18218-2018', '1', '氯乙烯', '乙烯基氯', '75-01-4', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('7dbf76ec-571f-5406-b171-e19e1d47d1a5', 'GB18218-2018', '1', '氢', '氢气', '1333-74-0', 5, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('0f7c21d6-44ca-5e4d-8da2-8794ab4d2702', 'GB18218-2018', '1', '液化石油气(含丙烷、丁烷及其混合物)', '石油气(液化的)', '68476-85-7；74-98-6(丙烷)；106-97-8(丁烷)', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('17d6547c-cdcf-5da0-b506-a243d5902f99', 'GB18218-2018', '1', '一甲胺', '氨基甲烷;甲胺', '74-89-5', 5, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('96862992-a066-5b46-9cfb-fd1ac7135f4b', 'GB18218-2018', '1', '乙炔', '电石气', '74-86-2', 1, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('e4770c5b-3e19-5f6f-8f6e-bf2ed278a75a', 'GB18218-2018', '1', '乙烯', NULL, '74-85-1', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('07045d29-b024-5c2e-8d9e-1dcddc465561', 'GB18218-2018', '1', '氧(压缩的或液化的)', '液氧;氧气', '7782-44-7', 200, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('d8860ec9-3ce8-5387-8a56-0d1cba9dd55f', 'GB18218-2018', '1', '苯', '纯苯', '71-43-2', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('31e5ee48-31db-5b34-9f4e-c89c886dfb58', 'GB18218-2018', '1', '苯乙烯', '乙烯苯', '100-42-5', 500, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('e83d3155-f068-51fc-a0c1-e131f0aa92f6', 'GB18218-2018', '1', '丙酮', '二甲基酮', '67-64-1', 500, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('7089dc4a-2bf4-5629-b797-7fb867e101b4', 'GB18218-2018', '1', '2-丙烯腈', '丙烯腈;乙烯基氰;氰基乙烯', '107-13-1', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('795e9f05-fb3c-5d31-87e0-b3e05c9d1e67', 'GB18218-2018', '1', '二硫化碳', NULL, '75-15-0', 50, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('a7e7c216-87eb-58b1-83e4-502e2595666c', 'GB18218-2018', '1', '环己烷', '六氢化苯', '110-82-7', 500, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('4a969172-fc79-50e7-ba15-0c1e227cf1a6', 'GB18218-2018', '1', '1,2-环氧丙烷', '氧化丙烯;甲基环氧乙烷', '75-56-9', 10, NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('13191471-a2d0-5346-8851-5668f8c5f354', 'GB18218-2018', '1', '甲苯', '甲基苯;苯基甲烷', '108-88-3', 500, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c9cc3d60-43f0-5bb5-8c95-2c1fa8fc5478', 'GB18218-2018', '1', '甲醇', '木醇;木精', '67-56-1', 500, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c4422395-f195-550b-9a5d-a9dcccfaa50a', 'GB18218-2018', '1', '汽油(乙醇汽油、甲醇汽油)', NULL, '86290-81-5(汽油)', 200, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('892c96b1-c9b3-58b8-8753-512deccff80d', 'GB18218-2018', '1', '乙醇', '酒精', '64-17-5', 500, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('2ab7fb6b-91d7-5b5e-9c10-a9ccbe70eacf', 'GB18218-2018', '1', '乙醚', '二乙基醚', '60-29-7', 10, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('fa2c48d8-b53a-5157-9032-c02591a35a24', 'GB18218-2018', '1', '乙酸乙酯', '醋酸乙酯', '141-78-6', 500, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('b864c89d-ed84-5db6-9e6f-67dab7dc5b26', 'GB18218-2018', '1', '正己烷', '己烷', '110-54-3', 500, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('654830d8-3d1b-5e58-ae97-fd783ab176f2', 'GB18218-2018', '1', '过乙酸', '过醋酸;过氧乙酸;乙酰过氧化氢', '79-21-0', 10, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('3e33734d-fe04-5b77-867c-9fbbb554cdb5', 'GB18218-2018', '1', '过氧化甲基乙基酮(10%<有效氧含量≤10.7%,含A型稀释剂≥48%)', NULL, '1338-23-4', 10, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('f1a94ef1-36b0-5dd4-83ff-0547586c5665', 'GB18218-2018', '1', '白磷', '黄磷', '12185-10-3', 50, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('70efeefb-1480-5dae-80ef-3f3349779f60', 'GB18218-2018', '1', '烷基铝', '三烷基铝', NULL, 1, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('5cba452b-586a-5bde-9757-0b53ef5bac74', 'GB18218-2018', '1', '戊硼烷', '五硼烷', '19624-22-7', 1, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c985bd36-efe3-515a-b690-34c9356a1b55', 'GB18218-2018', '1', '过氧化钾', NULL, '17014-71-0', 20, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('27c7658b-5e78-5151-a185-4580bc896932', 'GB18218-2018', '1', '过氧化钠', '双氧化钠;二氧化钠', '1313-60-6', 20, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('a93d4b74-e4ad-597f-95b2-814bd6410654', 'GB18218-2018', '1', '氯酸钾', NULL, '3811-04-9', 100, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('ef0853c7-299e-51c7-85f9-526bf21252a0', 'GB18218-2018', '1', '氯酸钠', NULL, '7775-09-9', 100, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('5a6470f7-ceec-5e35-ac57-7d9b1c13541e', 'GB18218-2018', '1', '发烟硝酸', NULL, '52583-42-3', 20, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('2542577d-8886-5ca3-a999-dadf28926826', 'GB18218-2018', '1', '硝酸(发红烟的除外,含硝酸>70%)', NULL, '7697-37-2', 100, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('54309de3-87a7-565c-bccd-8e7e89b52349', 'GB18218-2018', '1', '硝酸胍', '硝酸亚氨脲', '506-93-4', 50, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('c978b02d-1bb2-53e2-bacf-d8212d03af40', 'GB18218-2018', '1', '碳化钙', '电石', '75-20-7', 100, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('f3e836e8-19f7-56ea-aaf7-ead90aa70983', 'GB18218-2018', '1', '钾', '金属钾', '7440-09-7', 1, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) VALUES ('f2f459d1-92f6-50d0-84b9-035aa06902d5', 'GB18218-2018', '1', '钠', '金属钠', '7440-23-5', 10, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('ee67c9c6-0590-52df-83d1-93e856c0d79e', 'GB18218-2018', '2', '类别1,所有暴露途径,气体', '急性毒性', 'J1', 5, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('86df0079-2914-5473-9038-7e3de5cb2705', 'GB18218-2018', '2', '类别1,所有暴露途径,固体、液体', '急性毒性', 'J2', 50, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('f7138cea-7cc1-5513-a130-eb95bc08025a', 'GB18218-2018', '2', '类别2、类别3,所有暴露途径,气体', '急性毒性', 'J3', 50, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('e5190d68-6e45-55c3-8284-8c8f27d90382', 'GB18218-2018', '2', '类别2、类别3,吸入途径,液体(沸点≤35℃)', '急性毒性', 'J4', 50, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('e36449b5-0325-5c19-9ce0-62eab9e05527', 'GB18218-2018', '2', '类别2,所有暴露途径,液体(除J4外)、固体', '急性毒性', 'J5', 500, NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('f3c0e43f-d279-5a68-8324-43072bd2ade6', 'GB18218-2018', '2', '—不稳定爆炸物—1.1项爆炸物', '爆炸物', 'W1.1', 1, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('2546cc70-1eb6-5090-b608-896e0f621934', 'GB18218-2018', '2', '1.2、1.3、1.5、1.6项爆炸物', '爆炸物', 'W1.2', 10, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('01659ade-a552-5d12-9a09-e0585d131296', 'GB18218-2018', '2', '1.4项爆炸物', '爆炸物', 'W1.3', 50, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('671ef131-70a4-523e-8066-f73c5e465672', 'GB18218-2018', '2', '类别1和类别2', '易燃气体', 'W2', 10, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('f243a21c-8b9e-5eb6-bd37-6bcec57d6ed8', 'GB18218-2018', '2', '类别1和类别2', '气溶胶', 'W3', 150, '150(净重)', 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('44aeff70-e781-5494-9351-e8f9bb4f970a', 'GB18218-2018', '2', '类别1', '氧化性气体', 'W4', 50, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('9975d83a-68ad-5d61-8e77-8639df5bbca9', 'GB18218-2018', '2', '—类别1—类别2和3,工作温度高于沸点', '易燃液体', 'W5.1', 10, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('16990f0f-fdf6-5d3f-a7e1-a0635509a7c5', 'GB18218-2018', '2', '—类别2和3,具有引发重大事故的特殊工艺条件包括危险化工工艺、爆炸极限范围或附近操作、操作压力大于1.6MPa等', '易燃液体', 'W5.2', 50, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('c9f1c27b-0f99-5e0f-b3ba-7d30790e9e07', 'GB18218-2018', '2', '—不属于W5.1或W5.2的其他类别2', '易燃液体', 'W5.3', 1000, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('f04f7984-f5c0-54c3-b836-48b98688b021', 'GB18218-2018', '2', '—不属于W5.1或W5.2的其他类别3', '易燃液体', 'W5.4', 5000, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('148f5be7-d731-5ae7-b958-43f2a090289c', 'GB18218-2018', '2', 'A型和B型自反应物质和混合物', '自反应物质和混合物', 'W6.1', 10, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('2e6ecb5e-3407-517c-89a6-94d3f36c547a', 'GB18218-2018', '2', 'C型、D型、E型自反应物质和混合物', '自反应物质和混合物', 'W6.2', 50, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('ad10d7c3-8742-52ce-b224-d19c2bc93af0', 'GB18218-2018', '2', 'A型和B型有机过氧化物', '有机过氧化物', 'W7.1', 10, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('d6421ede-14b7-57d4-9c36-e47c40a00e67', 'GB18218-2018', '2', 'C型、D型、E型、F型有机过氧化物', '有机过氧化物', 'W7.2', 50, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('56332134-0462-5ae8-b044-93defcab78c1', 'GB18218-2018', '2', '类别1自燃液体类别1自燃固体', '自燃液体和自燃固体', 'W8', 50, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('47516462-6390-5e28-8796-d5c88e1c78ea', 'GB18218-2018', '2', '类别1', '氧化性固体和液体', 'W9.1', 50, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('96d8b6ff-03e3-52e6-b4c7-e25af2c00561', 'GB18218-2018', '2', '类别2、类别3', '氧化性固体和液体', 'W9.2', 200, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('e74ede8e-d641-55b3-a376-a008df1a1296', 'GB18218-2018', '2', '类别1易燃固体', '易燃固体', 'W10', 200, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO critical_quantities (id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) VALUES ('f0b4ec48-4c4e-5c6b-ac2f-0a9e3f687f2b', 'GB18218-2018', '2', '类别1和类别2', '遇水放出易燃气体的物质和混合物', 'W11', 200, NULL, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('2552955c-a25f-58b6-bd68-6606ceb3e292', 'GB18218-2018', '3', '一氧化碳', 2, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('2175fdd3-c2c7-5918-82ef-4045020071f4', 'GB18218-2018', '3', '二氧化硫', 2, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('f8a3afbe-469f-5798-8e0a-f5c0075e05ba', 'GB18218-2018', '3', '氨', 2, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('a37b2fc0-6f53-5374-a272-32afa7b2a422', 'GB18218-2018', '3', '环氧乙烷', 2, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('8b062487-8092-5666-a52f-29aa1a1489ce', 'GB18218-2018', '3', '氯化氢', 3, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('dffa49dd-03f1-5e3e-8d55-1c7159c4c79d', 'GB18218-2018', '3', '溴甲烷', 3, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('32e9f549-b026-57b5-9a3d-8b3842c64113', 'GB18218-2018', '3', '氯', 4, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('c821ace0-7e48-5646-a876-cb74fa29943c', 'GB18218-2018', '3', '硫化氢', 5, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('541dfc1a-1332-5485-a33b-f4aee70983b3', 'GB18218-2018', '3', '氟化氢', 5, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('e28f6de6-af61-5d2b-bb30-77762be854dd', 'GB18218-2018', '3', '二氧化氮', 10, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('6d030c29-3d9e-5ff4-932f-61bfceefb4d7', 'GB18218-2018', '3', '氰化氢', 10, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('1509fd60-eda2-5bfb-8fe6-3a2f6e70a246', 'GB18218-2018', '3', '碳酰氯', 20, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('f5583c9e-a403-5f50-bf6f-23f9ede0bfcd', 'GB18218-2018', '3', '磷化氢', 20, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, chemical_name, beta, source_page) VALUES ('5b0e436a-a3a1-58d4-89ea-099c65e07808', 'GB18218-2018', '3', '异氰酸甲酯', 20, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('50ce3c6e-3c76-5659-8aab-2d579ad1b5b6', 'GB18218-2018', '4', '急性毒性', 'J1', 4, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('046c0269-b3d4-5e15-b4a2-98230cf6dfe9', 'GB18218-2018', '4', '急性毒性', 'J2', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('c1db9cfa-4944-594e-8001-f6b4b2168edd', 'GB18218-2018', '4', '急性毒性', 'J3', 2, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('e578800e-1e65-5560-b868-446c010911af', 'GB18218-2018', '4', '急性毒性', 'J4', 2, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('4a53d053-5092-5787-a9fc-4c22c2659b4c', 'GB18218-2018', '4', '急性毒性', 'J5', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('669a5bdb-74e0-5546-afe4-22b636d9975c', 'GB18218-2018', '4', '爆炸物', 'W1.1', 2, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('02241be8-bf84-50f4-96e0-c40d65bb3527', 'GB18218-2018', '4', '爆炸物', 'W1.2', 2, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('ceed2a73-fcf6-5ded-877e-24778b16ae5d', 'GB18218-2018', '4', '爆炸物', 'W1.3', 2, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('5b1ec7d9-3ce8-55d9-8cd0-124974e3d832', 'GB18218-2018', '4', '易燃气体', 'W2', 1.5, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('2a3f29e2-47b3-5d1e-819d-4cf4d157a936', 'GB18218-2018', '4', '气溶胶', 'W3', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('95ce57a4-3c2b-5ff4-a0a4-379e359d6f48', 'GB18218-2018', '4', '氧化性气体', 'W4', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('ca1fd7de-7434-5c28-8f15-44306dc2c954', 'GB18218-2018', '4', '易燃液体', 'W5.1', 1.5, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('a77843c6-6071-5788-b9a3-ed28548bd77b', 'GB18218-2018', '4', '易燃液体', 'W5.2', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('7de02ce6-de2d-5abd-a15d-4c5a96bacc27', 'GB18218-2018', '4', '易燃液体', 'W5.3', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('7b859835-0cdf-5c3f-80c0-f2a2791e5c21', 'GB18218-2018', '4', '易燃液体', 'W5.4', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('3a6c6766-0454-58a8-a92d-a24f27c494e0', 'GB18218-2018', '4', '自反应物质和混合物', 'W6.1', 1.5, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('88337363-240b-5c7f-b19d-a5dd8b017a23', 'GB18218-2018', '4', '自反应物质和混合物', 'W6.2', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('ec7e329d-c148-53c3-80b8-c802a0fd8651', 'GB18218-2018', '4', '有机过氧化物', 'W7.1', 1.5, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('16aeb772-d5b0-54e2-9252-6f9ae79a0978', 'GB18218-2018', '4', '有机过氧化物', 'W7.2', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('8db51f08-936a-5f13-8c39-6ce1c6646991', 'GB18218-2018', '4', '自燃液体和自燃固体', 'W8', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('c3eab689-ad87-5319-a387-b9a660272d55', 'GB18218-2018', '4', '氧化性固体和液体', 'W9.1', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('9dfe159e-0e43-564d-874a-063599920f10', 'GB18218-2018', '4', '氧化性固体和液体', 'W9.2', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('8dca3731-5c5d-5062-b2ba-3c28b14e008c', 'GB18218-2018', '4', '易燃固体', 'W10', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO hazard_beta_factors (id, standard, source_table, category, symbol, beta, source_page) VALUES ('3e5ffb78-e00f-566c-81ce-8bfb42962015', 'GB18218-2018', '4', '遇水放出易燃气体的物质和混合物', 'W11', 1, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO exposure_alpha_factors (id, standard, label, population_min, population_max, alpha, source_page) VALUES ('d86fa80a-a05f-5404-b5eb-1202a0acc907', 'GB18218-2018', '100人以上', 100, NULL, 2.0, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO exposure_alpha_factors (id, standard, label, population_min, population_max, alpha, source_page) VALUES ('5f7279ef-a52d-5fc4-ade9-fce80dcc7c2b', 'GB18218-2018', '50~99人', 50, 99, 1.5, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO exposure_alpha_factors (id, standard, label, population_min, population_max, alpha, source_page) VALUES ('074cb833-4fd6-5c09-84f7-de42343f942d', 'GB18218-2018', '30~49人', 30, 49, 1.2, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO exposure_alpha_factors (id, standard, label, population_min, population_max, alpha, source_page) VALUES ('8db83bcb-6b17-5783-ba46-57d64b855bba', 'GB18218-2018', '1~29人', 1, 29, 1.0, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO exposure_alpha_factors (id, standard, label, population_min, population_max, alpha, source_page) VALUES ('f8ce06ea-d6c8-53b5-8637-aeea027940b9', 'GB18218-2018', '0人', 0, 0, 0.5, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO major_hazard_levels (id, standard, level_name, r_expression, r_min, r_max, source_page) VALUES ('43d46575-126d-5ac9-bbd9-cc3c591db61c', 'GB18218-2018', '一级', 'R≥100', 100, NULL, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO major_hazard_levels (id, standard, level_name, r_expression, r_min, r_max, source_page) VALUES ('621b0f71-4087-5b58-b7c1-5f5fc330a615', 'GB18218-2018', '二级', '100>R≥50', 50, 100, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO major_hazard_levels (id, standard, level_name, r_expression, r_min, r_max, source_page) VALUES ('e018569e-bdb8-55db-81d0-5858993d2d17', 'GB18218-2018', '三级', '50>R≥10', 10, 50, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO major_hazard_levels (id, standard, level_name, r_expression, r_min, r_max, source_page) VALUES ('d4a064b1-c9e4-5816-9c94-6c2422ab08a5', 'GB18218-2018', '四级', 'R<10', NULL, 10, 11) ON CONFLICT (id) DO NOTHING;
