-- 20260921 作业票措施条件映射（由 seed_work_ticket_conditions.py 生成，勿手改）
-- 幂等：先按票种清理再插入。锚定键 measure_ref = 措施正文规范化后的 sha256 前 32 位。
BEGIN;

CREATE TABLE IF NOT EXISTS work_ticket_measure_conditions (
    id            UUID PRIMARY KEY,
    ticket_type   VARCHAR(20) NOT NULL,
    measure_ref   VARCHAR(64) NOT NULL,
    sort_order    INTEGER NOT NULL,
    condition_key VARCHAR(60) NOT NULL,
    UNIQUE (ticket_type, measure_ref, condition_key)
);
CREATE INDEX IF NOT EXISTS idx_wtmc_type ON work_ticket_measure_conditions(ticket_type);

CREATE TABLE IF NOT EXISTS work_ticket_scenarios (
    id            UUID PRIMARY KEY,
    ticket_type   VARCHAR(20) NOT NULL,
    condition_key VARCHAR(60) NOT NULL,
    label         VARCHAR(200) NOT NULL,
    auto_rule     VARCHAR(60) NULL,
    sort_order    INTEGER NOT NULL,
    UNIQUE (ticket_type, condition_key)
);

DELETE FROM work_ticket_measure_conditions WHERE ticket_type = 'DHZY';
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('e50cb522-992a-5c5e-b66d-f02b76c69315', 'DHZY', 'aa152327dcc776c3b2401f6c038c9c2c', 1, 'internal_work') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('db9d65df-7a44-5f65-91ba-5270b857fadd', 'DHZY', 'b9bacced278411f47a7f16e635f0c82e', 2, 'connected_pipeline') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('5a400145-ee81-5479-bbb6-7ded6e6d084b', 'DHZY', 'c438375fa35946cd8418e70eb87f5f33', 3, 'surroundings_ignition') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('d98ebd5f-09b4-55e6-83c1-e9ae94731936', 'DHZY', '2bbf4531b74b9091350219a96f06b76b', 4, 'in_tank_area') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('94fb6342-ce18-537f-828d-bb87a12c64ea', 'DHZY', '182ff7686db6901df293e7721f5335ff', 5, 'height_work') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('a8ee7ce5-33e9-513a-87e9-5193674cbbdc', 'DHZY', '9dc7f7d88889658d724328bc16bd4659', 6, 'has_flammable_lining') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('f0ce8e10-92da-5c25-b33a-65a3a06f526e', 'DHZY', '1a79fe85f5988f7bb6464827f39b9ac8', 7, 'gas_welding') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('7deb681c-5251-5ae9-9695-188131d6d4b3', 'DHZY', '5506f7bfc406130f03777a9849cfa946', 9, 'electric_welding') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('b918127e-7ffa-5e3c-8cde-c1e644959d94', 'DHZY', '866faaee45c17dddf8e35d6384e73e78', 10, 'surrounding_hazardous_ops') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('328d87c9-942f-5c02-bc7c-9aec0180ec85', 'DHZY', '9ab6da52395e125472eab40c34233087', 11, 'surrounding_hazardous_ops') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('e6cefe6d-208b-541e-9755-006f8ec9ad0a', 'DHZY', 'a7f3037ebc30c4f33dfd888b127c769e', 12, 'has_other_tickets') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('2fcd606a-5e64-511f-8140-9e5ede5ad04f', 'DHZY', '37618b07a8f136ff57b0c04ccc664ccb', 13, 'gas_welding') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('ae1a32f0-45fe-513a-9e52-315cf9502b4f', 'DHZY', '37618b07a8f136ff57b0c04ccc664ccb', 13, 'electric_welding') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('d5ba6050-9ffe-592e-a3da-a97b08040a0e', 'DHZY', '08ed389dc66b90f4527bdd891fb09548', 15, 'has_other_tickets') ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_measure_conditions WHERE ticket_type = 'YXKJ';
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('0af9ad74-998d-58b8-8c37-81563ba36ed8', 'YXKJ', 'f14a34f23d3e38ea6d1518da0e200ec6', 1, 'hazardous_residue') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('6d823131-abfd-5e5d-8679-fc2eaeaba36f', 'YXKJ', 'f14a34f23d3e38ea6d1518da0e200ec6', 1, 'connected_pipeline') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('e6029e61-d1b1-5e32-9e01-18abf89ea64e', 'YXKJ', '06ba0bda9ff04ab8f197b570a751331b', 2, 'hazardous_residue') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('815b8cb1-af54-5aa9-9746-2e7d7a3768ff', 'YXKJ', 'c74829c85a9a1dabd9cec5d10cf41173', 4, 'rotating_equipment') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('2cc4646f-8398-54e9-8081-9af08445140a', 'YXKJ', 'df8d5742b8f91a8da8bd79f60e63a24e', 5, 'flammable_atmosphere') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('4ac4f779-f02e-53d9-b008-86a9fcd6f31e', 'YXKJ', '4c3f8b4c9de0cf3d680e119504b12209', 7, 'hazardous_residue') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('fc217eb6-bebe-52cb-a3d2-7e437a0a6969', 'YXKJ', '6cf01ad60f941d3a3ed982e46991e8cb', 8, 'dust_inside') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('b5340885-bd9b-5e0f-8d3c-ae2e5024e270', 'YXKJ', '8f340f0cf66f100e8ff26a40d03cc4e3', 11, 'corrosive_medium') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('365d13b5-e4b2-5305-889b-1094ee8917c5', 'YXKJ', '1167038c51b14862c6bef378fc2edcc5', 14, 'has_other_tickets') ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_measure_conditions WHERE ticket_type = 'MBCD';
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('40eb1283-1f87-5504-a2c5-fd1620ddd2ca', 'MBCD', '376567c2bcc3f39149e4383d95527318', 2, 'toxic_medium') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('3d250ffb-0845-50d5-a235-424330016183', 'MBCD', '1cf38f5ab2a1b52a120beb59b145d9cc', 3, 'explosion_hazard_area') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('90f219cc-d38a-5fca-bafb-13f28b05df02', 'MBCD', 'c9b7928fa55e62141108ebb3b23d2b7b', 4, 'explosion_hazard_area') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('9411c2a9-0c7a-5257-8e13-b42548629cfb', 'MBCD', 'be9faa60bc042af562142995c56bff2c', 5, 'corrosive_medium') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('c15f1e5f-aff8-5014-9044-b8a73115b93d', 'MBCD', '257cf13fdcbac6367533c4e4f15cd694', 6, 'high_temp_medium') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('31db4491-8456-54e1-bdf7-ba0f72eafa9a', 'MBCD', '9bd06a1ab69e766a2df26fcd81c937d1', 7, 'low_temp_medium') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('3b5443a2-9ead-55d9-9dc7-c68ed8a30263', 'MBCD', 'a563191e088cff4fed89f83bfc084069', 8, 'multi_point_same_pipe') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('338cc708-775e-59a3-ae8a-bae63db070da', 'MBCD', '1167038c51b14862c6bef378fc2edcc5', 9, 'has_other_tickets') ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_measure_conditions WHERE ticket_type = 'GCZY';
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('dcd0ffba-41da-58fd-8ef7-dd7562584ef0', 'GCZY', '56af4fa4fa67b0e91fcb9a0d6ad17e9f', 3, 'toxic_gas_area') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('4e82e4fa-69d1-5951-9808-35b2c4e67739', 'GCZY', 'abcfcebd2e69f6a6c4d60420ecc66345', 5, 'scaffold_used') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('9b2c0f53-eddd-5582-8a4e-edadd4af5c5f', 'GCZY', '534a8ae685781dbf7a285072010fe063', 6, 'layered_work') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('1e6529e6-3b5a-513d-a0d2-2fcd60476312', 'GCZY', 'a35d280f705a23f307d7efe241079cad', 7, 'ladder_used') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('0168011b-fd00-556b-8637-1a7deb453365', 'GCZY', '8ec570890221e5a769a07d9320b03622', 8, 'light_shed') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('83bf5904-27c7-5efb-9b99-286d425f2ef9', 'GCZY', '1d173f5ff64da7a33452b58a42a7d9a3', 9, 'load_bearing_plate') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('89f81ceb-9a32-554f-9a5b-27af1ad4e366', 'GCZY', 'c1dda3bf48394976f8fc48eb84d9b81a', 10, 'night_or_poor_light') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('04b246a4-c89c-533a-a761-fc9acb1ff747', 'GCZY', '7638170ba2b5d7ee94466157f9786ee9', 11, 'above_30m') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('c5e9a9cb-23b6-5fd6-8a1e-d0738b10f28a', 'GCZY', 'ac23cbd7382000ae62d1c7f5ba2844aa', 13, 'outdoor') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('72451158-e6c7-5fb1-bc75-1da30579128c', 'GCZY', '1167038c51b14862c6bef378fc2edcc5', 14, 'has_other_tickets') ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_measure_conditions WHERE ticket_type = 'QZDZ';
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('031fb5fa-2cc4-5c29-b704-07a5250541ac', 'QZDZ', '5021845c6846dacb500d9df32e914ec8', 1, 'level_1_or_2') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('c0afe30a-48c8-5328-8cba-4ada5719ccdf', 'QZDZ', '1c0d321eaa09cc97cf8db5fb63a6dade', 2, 'hazardous_equipment_nearby') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('27eea766-697a-5395-aa94-304a9d6b5779', 'QZDZ', 'f88d7a2a66752e992fcfc3aa085c281b', 6, 'building_as_anchor') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('23284e1e-51dd-5106-acca-20eb3f75e7f1', 'QZDZ', '2896a66fc1bf3deadee463145bd7eebd', 7, 'near_power_line') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('a4e39493-c9da-5cd5-abc3-45206b2a7054', 'QZDZ', '6ee007178cfd7ffdd1025dd9a4fa97ca', 8, 'pipe_as_anchor') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('f47c843c-08a8-5dff-8d9f-3d66efa21bd9', 'QZDZ', '33cbacbf5b4f041ae3e337fb05e053dd', 12, 'underground_facilities') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('fe9490e7-0c8d-5487-ad09-ceffde8c2054', 'QZDZ', '195d51e2e3a2d52697a2796290eec48f', 14, 'overhead_facilities') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('8c1f858d-8843-542c-baef-f8b0fbe7eed3', 'QZDZ', '90b5e8402439d5a35e1257e7e927bf45', 16, 'near_power_line') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('1bd499ed-351e-5e83-8362-47f69f2c8475', 'QZDZ', '18e2d9d7b9509ec561e453fe519d237d', 17, 'explosion_hazard_area') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('23ecdb82-c11d-5502-ac18-373492bd9a15', 'QZDZ', 'b2febccc47fd5df9900d7e0c8f6e9c35', 18, 'outdoor') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('9229e42c-e2e9-516a-8002-b270fc6eb40c', 'QZDZ', '1167038c51b14862c6bef378fc2edcc5', 19, 'has_other_tickets') ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_measure_conditions WHERE ticket_type = 'LSYD';
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('d13a9761-793a-58c6-a4dc-54134f842b91', 'LSYD', '29ccbf76d5f185e51fde089e95cd03d3', 2, 'explosion_hazard_area') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('4f97275e-b496-5fe9-9f33-0761d7cec270', 'LSYD', '693e46aeca2ab00f83293b3dcb192185', 5, 'line_elevated') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('79c4f373-2a56-5af9-8e81-c990ff0d21df', 'LSYD', '9b509926c43dd4ec5e7d3d684fce7118', 6, 'line_along_surface') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('fbdfff5d-4d9f-599c-bd5b-afdebe6a9377', 'LSYD', '9b509926c43dd4ec5e7d3d684fce7118', 6, 'cross_road') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('c532aaae-38ee-5b4b-936a-b52a7cecf48c', 'LSYD', 'e6fecf7ed99fa9f19fcbae5af3808589', 7, 'line_elevated') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('d6649108-5d70-5e44-8917-19ba5528bd85', 'LSYD', '15c4f1a8f49a080f4874238c9b82b76c', 8, 'underground_cable') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('cbd57084-ac24-57cc-b50e-83acdf7977f3', 'LSYD', 'dd286b8b3b09e11ec3d905762bc760c7', 9, 'outdoor') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('f809c319-aeef-5ab7-ab9f-a43f47511a17', 'LSYD', '1167038c51b14862c6bef378fc2edcc5', 12, 'has_other_tickets') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('ed774326-c9eb-541f-8117-f538cfe329f3', 'LSYD', 'e98eb50e56253e08310fad1c074f9e88', 13, 'explosion_hazard_area') ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_measure_conditions WHERE ticket_type = 'PTZY';
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('14f6107f-81b3-534a-bcfa-4a635a6f6756', 'PTZY', 'f87522fd6afc5717c80086ba613fde57', 1, 'underground_cable') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('5f98342a-393d-50e1-ad1f-249d568ef0ee', 'PTZY', 'f01a1ffed3906ec1f1248339caff7f7f', 2, 'underground_pipeline') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('499fcbc8-7af6-5f57-90a1-77f73290b783', 'PTZY', 'eca63dde6b81e2cb1ec5815159eb95b9', 5, 'deep_excavation') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('a528f48a-b668-5bf7-b755-e4f7e884001d', 'PTZY', 'cf979fb3c177d333b71bb10d70e81ea1', 6, 'on_road') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('a590ab3f-d95f-5405-8c7b-4362c3fdce4e', 'PTZY', '14d68119728c367c4b5542b3665ca838', 7, 'night_work') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('309d2496-b887-5d56-92fd-4475ee8b31e9', 'PTZY', '605e6576e6577466127c263dc54e7d58', 9, 'deep_excavation') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('7c2a4696-088e-5483-bedf-a80b565ec2d6', 'PTZY', '605e6576e6577466127c263dc54e7d58', 9, 'hazardous_area') ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('c8c0bbb8-b8db-5cca-92ed-b203a379845a', 'PTZY', '1167038c51b14862c6bef378fc2edcc5', 10, 'has_other_tickets') ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_measure_conditions WHERE ticket_type = 'DLZY';
INSERT INTO work_ticket_measure_conditions (id, ticket_type, measure_ref, sort_order, condition_key) VALUES ('b7a09461-d6ab-5f5e-bcfd-b5bd1fd2b366', 'DLZY', '151379bfa1dbf376492052054e9fba32', 3, 'night_work') ON CONFLICT (id) DO NOTHING;

-- 情景项（仅人工勾选项；自动推断项不入情景区）
DELETE FROM work_ticket_scenarios WHERE ticket_type = 'DHZY';
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('225dd995-0851-5eb6-8394-be02c6b64d11', 'DHZY', 'internal_work', '本次动火在设备内部', NULL, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('f193439c-cb95-53fc-9f11-9e36c2712da2', 'DHZY', 'connected_pipeline', '作业设备连接有管线/阀门', NULL, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('b62c700d-4b89-57d5-98db-85dde50948d8', 'DHZY', 'surroundings_ignition', '作业点周围有孔洞/窨井/地沟/污水井', NULL, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('a9010420-e8b2-5c8b-b629-84df064887f1', 'DHZY', 'in_tank_area', '作业点在油气罐区防火堤内', NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('438a340f-8ef9-5f59-965e-7136dbc0c4e0', 'DHZY', 'height_work', '本次作业涉及高处作业', NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('404d20bd-df5f-5353-9887-fbc8d3087385', 'DHZY', 'has_flammable_lining', '设备内有可燃物构件或防腐内衬', NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('91215b41-cf98-5ec3-a819-1623afb0ad4a', 'DHZY', 'surrounding_hazardous_ops', '作业点周围有装卸/排放/喷漆等危险作业', NULL, 7) ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_scenarios WHERE ticket_type = 'YXKJ';
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('55f2371d-d58a-5365-bcad-8b37face39d0', 'YXKJ', 'hazardous_residue', '受限空间盛装过有毒/可燃物料', NULL, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('4dae7c4d-8449-589c-87b3-bbb0078b711d', 'YXKJ', 'connected_pipeline', '作业设备连接有管线/阀门', NULL, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('203ea588-5e70-5a72-b47f-4547680dd2d6', 'YXKJ', 'rotating_equipment', '内部有转动设备', NULL, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('e6b214a9-efd4-590a-baec-d8fb9201aadb', 'YXKJ', 'flammable_atmosphere', '内部存在易燃易爆物料', NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('32d47f2b-dd4e-5d7c-9b4e-dc23977bed64', 'YXKJ', 'dust_inside', '内部存在大量扬尘', NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('910f549c-5fef-5d16-b2ce-2ff96d2c43d6', 'YXKJ', 'corrosive_medium', '存在强腐蚀性介质', NULL, 6) ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_scenarios WHERE ticket_type = 'MBCD';
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('2eed872c-1c59-5257-a91f-dac0a25b4c52', 'MBCD', 'toxic_medium', '存在有毒介质', NULL, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('8518b66c-7d72-5a06-a258-6ab57b0e3a7e', 'MBCD', 'explosion_hazard_area', '作业点在火灾爆炸危险场所', NULL, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('37fdbcdf-d3d3-5b3b-981a-a39a5d291f74', 'MBCD', 'corrosive_medium', '存在强腐蚀性介质', NULL, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('3070f7b5-3b37-5e6c-95e7-7cdfeb9340b0', 'MBCD', 'high_temp_medium', '介质温度较高（可能烫伤）', NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('34d5bbe3-6480-56f5-ab94-2c854d297462', 'MBCD', 'low_temp_medium', '介质温度较低（可能冻伤）', NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('c29d46c6-e242-5b6b-a8b8-7d757ecb56e9', 'MBCD', 'multi_point_same_pipe', '同一管道多处同时抽堵', NULL, 6) ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_scenarios WHERE ticket_type = 'GCZY';
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('f9e88a07-86af-5073-8688-db28907014e6', 'GCZY', 'toxic_gas_area', '作业点可能散发有毒气体', NULL, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('4fcbd78b-c253-5218-95d5-7ed60ad079ed', 'GCZY', 'scaffold_used', '现场搭设脚手架/防护网', NULL, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('e74ac329-73d0-5473-8c25-51388446962f', 'GCZY', 'layered_work', '垂直分层作业', NULL, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('0204905d-a54a-51f9-aca0-4d076bcc6811', 'GCZY', 'ladder_used', '使用梯子/安全绳', NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('fb8711db-d54f-5b8e-9567-2ff87d6100db', 'GCZY', 'light_shed', '作业处有轻型棚', NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('5393e1c2-6719-5419-af98-45d850740eca', 'GCZY', 'load_bearing_plate', '在不承重物处作业并搭设承重板', NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('0db9a23d-0050-59f4-bf91-38dcc9a8ff4f', 'GCZY', 'night_or_poor_light', '夜间作业或采光不足', NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('c6faa06b-66d9-5d8b-8040-7a821fa067a9', 'GCZY', 'outdoor', '露天作业', NULL, 8) ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_scenarios WHERE ticket_type = 'QZDZ';
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('f2608605-d360-53e7-9fca-9d9fd61e1b50', 'QZDZ', 'hazardous_equipment_nearby', '吊装场所含危险物料的设备/管道', NULL, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('3fb37823-e035-54b5-b242-f396af8d2ed2', 'QZDZ', 'building_as_anchor', '以建筑物/构筑物作锚点', NULL, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('c6906209-60e5-50a6-8719-d6941c66bf48', 'QZDZ', 'near_power_line', '吊装范围附近有带电线路/架空线路', NULL, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('f3496050-5b99-541c-b614-5e21fa9422ca', 'QZDZ', 'pipe_as_anchor', '以管道/管架作吊装锚点', NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('3359d389-928d-563d-b17d-82f05a1d6f4b', 'QZDZ', 'underground_facilities', '吊装区域地下有电缆/管线/排水沟', NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('f1ec4bb9-df7e-59c3-8cc4-69d47d219eed', 'QZDZ', 'overhead_facilities', '吊装高度有管线/电缆桥架', NULL, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('959618ae-c42f-5504-8d51-6fca77722c04', 'QZDZ', 'explosion_hazard_area', '作业点在火灾爆炸危险场所', NULL, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('2a8a95d0-db20-51a6-b653-527c188b274d', 'QZDZ', 'outdoor', '露天作业', NULL, 8) ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_scenarios WHERE ticket_type = 'LSYD';
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('388c17aa-a9e3-53f9-8e20-0c17af410c7e', 'LSYD', 'explosion_hazard_area', '作业点在火灾爆炸危险场所', NULL, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('1a873c64-bf65-5187-846a-328e5c6e10eb', 'LSYD', 'line_elevated', '临时用电线路架高敷设', NULL, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('8cc6fe44-2697-53c2-a4f4-ebd75a323371', 'LSYD', 'cross_road', '线路跨越道路', NULL, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('443b8ffc-e342-5491-8921-5dbc17d5712e', 'LSYD', 'line_along_surface', '线路沿墙面或地面敷设', NULL, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('3f8ac22a-b546-5ca3-824b-ac5160968394', 'LSYD', 'underground_cable', '有暗管埋设/地下电缆', NULL, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('7fa8a781-d73e-5a82-a9e2-8e4f5cc89d66', 'LSYD', 'outdoor', '露天作业', NULL, 6) ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_scenarios WHERE ticket_type = 'PTZY';
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('ffe6b273-b2c4-5c5c-9c0a-4bbba0d202e7', 'PTZY', 'underground_cable', '有暗管埋设/地下电缆', NULL, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('78bf7ee4-7a34-541d-abdb-95a8727b03b1', 'PTZY', 'underground_pipeline', '地下有供排水/消防/工艺管线', NULL, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('fed6b5cb-540d-560a-bb24-7265ae847175', 'PTZY', 'on_road', '在道路范围施工', NULL, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO work_ticket_scenarios (id, ticket_type, condition_key, label, auto_rule, sort_order) VALUES ('bcbe5bbf-5724-5255-876b-6aa64e3d40a7', 'PTZY', 'hazardous_area', '作业点存在易燃易爆/有毒气体', NULL, 4) ON CONFLICT (id) DO NOTHING;
DELETE FROM work_ticket_scenarios WHERE ticket_type = 'DLZY';

COMMIT;
