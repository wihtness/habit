from __future__ import annotations

from .models import HealthRule


def build_default_health_rules() -> tuple[HealthRule, ...]:
    return (
        HealthRule(
            id="health-breathing",
            symptom_type="气不够",
            danger_signals=("胸痛", "心悸", "头晕"),
            recommended_actions=("停止工作", "降温补水", "坐直", "缩唇呼吸"),
            avoid_actions=("继续高强度工作", "闷着硬扛"),
            medical_warning="若胸痛、心悸或头晕持续，请及时就医。",
        ),
        HealthRule(
            id="health-rhinitis",
            symptom_type="鼻塞/鼻炎",
            danger_signals=("呼吸明显困难",),
            recommended_actions=("盐水清洁鼻腔", "避开刺激", "湿润空气", "减少说话"),
            avoid_actions=("继续高刺激输出", "长时间处于刺激环境"),
            medical_warning="若症状明显加重，请寻求专业医生建议。",
        ),
        HealthRule(
            id="health-toothache",
            symptom_type="牙痛",
            danger_signals=("持续加重", "面部肿胀"),
            recommended_actions=("温水漱口", "牙线清理", "避免冷热甜硬刺激"),
            avoid_actions=("继续高刺激饮食", "长期拖延处理"),
            medical_warning="若疼痛持续或肿胀加重，请尽快看牙医。",
        ),
        HealthRule(
            id="health-mouth-ulcer",
            symptom_type="口腔溃疡",
            danger_signals=("持续不愈",),
            recommended_actions=("温盐水漱口", "清淡软食", "保持口腔清洁", "减少熬夜"),
            avoid_actions=("辛辣刺激", "继续晚睡"),
            medical_warning="若长时间不愈或反复严重，请咨询医生。",
        ),
        HealthRule(
            id="health-hips",
            symptom_type="腰臀久坐不适",
            danger_signals=("明显放射痛",),
            recommended_actions=("起身走动", "轻拉伸", "调整坐姿"),
            avoid_actions=("硬撑久坐", "猛烈拉伸"),
            medical_warning="若疼痛明显加剧或出现放射痛，请寻求专业评估。",
        ),
        HealthRule(
            id="health-overheat",
            symptom_type="脑力过热/想找刺激",
            danger_signals=(),
            recommended_actions=("离开座位", "喝水", "走动", "手机放远", "延迟 10 分钟"),
            avoid_actions=("继续刷刺激内容", "直接扩展任务"),
            medical_warning="这不是医疗诊断，只是恢复建议。",
        ),
        HealthRule(
            id="health-energy",
            symptom_type="偏瘦/能量低",
            danger_signals=(),
            recommended_actions=("下午加餐", "补水", "少量多次"),
            avoid_actions=("空腹硬工作",),
            medical_warning="若长期食欲低下或明显乏力，请咨询医生。",
        ),
        HealthRule(
            id="health-night",
            symptom_type="晚上兴奋/出汗",
            danger_signals=("明显不适持续",),
            recommended_actions=("停止深度工作", "三行收口", "洗澡或降温", "准备睡眠"),
            avoid_actions=("继续深度编码", "继续刺激娱乐"),
            medical_warning="若伴随明显躯体不适，请考虑就医。",
        ),
    )
