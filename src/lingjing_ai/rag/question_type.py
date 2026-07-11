from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionProfile:
    category: str
    label: str
    search_terms: tuple[str, ...]
    answer_focus: str


_PROFILES = (
    QuestionProfile(
        category="票务价格",
        label="ticket",
        search_terms=("门票", "票价", "价格", "多少钱", "收费", "优惠", "成人票", "学生票"),
        answer_focus="优先说明价格、优惠政策和购票提醒。",
    ),
    QuestionProfile(
        category="开放时间",
        label="hours",
        search_terms=("开放", "几点", "时间", "营业", "闭园", "入园", "公告", "场次"),
        answer_focus="优先说明开放时间、场次安排和以公告为准的提醒。",
    ),
    QuestionProfile(
        category="游览路线",
        label="route",
        search_terms=("路线", "怎么走", "游览", "顺序", "停车", "停车场", "自驾", "入口", "出口"),
        answer_focus="优先说明起点、顺序、路线和适合人群。",
    ),
    QuestionProfile(
        category="服务设施",
        label="service",
        search_terms=("老人", "老年", "长辈", "儿童", "婴儿车", "轮椅", "无障碍", "休息", "服务中心", "母婴"),
        answer_focus="优先说明服务位置、适合人群和使用提醒。",
    ),
    QuestionProfile(
        category="餐饮住宿",
        label="food_hotel",
        search_terms=("餐饮", "吃饭", "美食", "住宿", "酒店", "民宿", "餐厅"),
        answer_focus="优先说明餐饮住宿选择和游览中的实用提醒。",
    ),
    QuestionProfile(
        category="活动表演",
        label="show",
        search_terms=("表演", "演出", "活动", "节目", "灯光秀", "场次", "夜游"),
        answer_focus="优先说明活动内容、场次和确认公告的提醒。",
    ),
    QuestionProfile(
        category="景点介绍",
        label="attraction",
        search_terms=("景点", "特色", "有什么", "介绍", "文化", "历史", "风光"),
        answer_focus="优先说明核心特色、适合人群和游览建议。",
    ),
)

_DEFAULT_PROFILE = _PROFILES[-1]


def classify_question(question: str) -> QuestionProfile:
    return _classify(question)


def classify_content_category(content: str, section_path: str = "") -> str:
    return _classify(f"{section_path} {content}").category


def answer_focus_for_question(question: str) -> str:
    return classify_question(question).answer_focus


def _classify(text: str) -> QuestionProfile:
    normalized = text.lower()
    best_profile = _DEFAULT_PROFILE
    best_score = 0
    for profile in _PROFILES:
        score = sum(1 for term in profile.search_terms if term.lower() in normalized)
        if score > best_score:
            best_profile = profile
            best_score = score
    return best_profile
