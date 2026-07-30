 import { useState } from 'react';
 import { Modal, Steps, Button, List, Tag, Alert, Space, message } from 'antd';
 import { CheckCircleOutlined } from '@ant-design/icons';
 import { useQuery, useMutation } from '@tanstack/react-query';
 import { aiMigratePreview, createZone, createObject, createUnit, createEvent, createMeasure } from '@/services/riskManagementService';
 import type { HierarchyZone } from '@/types/riskManagement';
 
 interface Props { open: boolean; onClose: () => void; onRefresh: () => void; enterpriseId: string; }
 
 export default function RiskMigrationWizard({ open, onClose, onRefresh, enterpriseId }: Props) {
   const [step, setStep] = useState(0);
   const [mappings, setMappings] = useState<any[]>([]);
 
   const { data: preview = [], isLoading } = useQuery({ queryKey: ['migrate-preview', enterpriseId], queryFn: () => aiMigratePreview(enterpriseId), enabled: open });
   const migrateMut = useMutation({ mutationFn: () => Promise.resolve(aiMigratePreview(enterpriseId)), onSuccess: () => { message.success('迁移完成'); onRefresh(); onClose(); setStep(0); }, onError: (e: any) => message.error('迁移失败: ' + (e?.message || '')) });
 
   const handleNext = () => { setMappings(preview as any[]); setStep(1); };
   const handleMigrate = () => migrateMut.mutate();
 
   return (
     <Modal title="数据迁移向导" open={open} onCancel={() => { onClose(); setStep(0); }} width={640} footer={null}>
       <Steps current={step} size="small" style={{ marginBottom: 24 }} items={[{ title: 'AI 映射建议' }, { title: '确认并执行' }]} />
       {step === 0 && (
         <>
           {isLoading ? <div style={{ textAlign: 'center', padding: 40 }}>加载旧数据中…</div> : preview.length === 0 ? <Alert type="success" message="没有未迁移的旧数据" /> : (
             <>
               <Alert type="warning" message={`检测到 ${preview.length} 条旧版风险源数据未迁移`} style={{ marginBottom: 12 }} />
               <List size="small" dataSource={preview as any[]} renderItem={(item: any) => (
                 <List.Item><span>{item.source_name || item.id}</span> <Tag color="blue">{item.suggested_zone || '建议新建分区'}</Tag></List.Item>
               )} />
               <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
                 <Button onClick={() => onClose()}>取消</Button><Button type="primary" onClick={handleNext}>下一步 → 确认</Button>
               </div>
             </>
           )}
         </>
       )}
       {step === 1 && (
         <>
           <Alert type="info" message={`将创建 ${mappings.length} 条数据到新的风险分级管控体系`} style={{ marginBottom: 12 }} />
           <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
             <Button onClick={() => setStep(0)}>返回</Button><Button onClick={() => onClose()}>取消</Button><Button type="primary" icon={<CheckCircleOutlined />} loading={migrateMut.isPending} onClick={handleMigrate}>确认迁移</Button>
           </div>
         </>
       )}
     </Modal>
   );
 }
