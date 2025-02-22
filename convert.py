import json
from datetime import datetime, timedelta
import pytz
import re
import argparse 

# 节次时间映射表（仅用于节次列表格式）
TIME_SLOT_MAPPING = {
    1: ("07:50", "08:35"),
    2: ("08:40", "09:25"),
    3: ("09:45", "10:30"),
    4: ("10:35", "11:20"),
    5: ("11:25", "12:10"),
    6: ("14:00", "14:45"),
    7: ("14:50", "15:35"),
    8: ("15:55", "16:40"),
    9: ("16:45", "17:30"),
    10: ("17:35", "18:20"),
    11: ("19:30", "20:15"),
    12: ("20:20", "21:05"),
    13: ("21:10", "21:55"),
}


def parse_date_time_place(date_time_place):
    """
    解析 dateTimePlace，将其转换为多个 (weekday, start_time, end_time, location) 的列表。
    支持以下格式：
    1. GT-A403: 1(11,12,13)
    2. GT-B112: 7(08:30~12:30)
    3. GT-B112: 1(1,2,3);GT-B112: 3(08:30~12:30)
    """
    result = []
    segments = date_time_place.split(";")
    for segment in segments:
        try:
            # 使用正则表达式匹配预期格式
            match = re.match(r"(\S+):\s*(\d)\(([\d,~:]+)\)", segment.strip())
            if match:
                location = match.group(1)
                weekday = int(match.group(2))
                time_data = match.group(3).strip()

                if "~" in time_data:  # Handle time range format
                    start_time, end_time = map(str.strip, time_data.split("~"))
                    result.append((weekday, start_time, end_time, location))
                else:  # Handle periods format
                    units = list(map(int, time_data.split(",")))
                    start_time = TIME_SLOT_MAPPING[min(units)][0]
                    end_time = TIME_SLOT_MAPPING[max(units)][1]
                    result.append((weekday, start_time, end_time, location))
            else:
                raise ValueError(f"Invalid dateTimePlace format: {segment}")
        except Exception as e:
            raise ValueError(f"Invalid dateTimePlace format: {segment}") from e
    return result


def parse_weeks(week_text):
    """
    解析周数范围，返回一个列表（如 "1~10" -> [1, 2, ..., 10]）。
    """
    week_start, week_end = map(int, week_text.split("~"))
    return list(range(week_start, week_end + 1))


def generate_event(course, semester_start_date):
    """
    根据课程信息生成事件。
    """
    week_list = parse_weeks(course["weekText"]["text"])
    date_time_places = parse_date_time_place(course["dateTimePlace"]["text"])
    course_name = course["course"]["nameZh"]
    teacher = course["teachers"][0]["nameZh"] if course["teachers"] else "未知教师"

    events = []
    timezone = pytz.timezone("Asia/Shanghai")  # Define the timezone

    for week in week_list:
        for weekday, start_time, end_time, location in date_time_places:
            # Calculate the event date based on the provided weekday
            # Adjusted to ensure that 1 = Sunday, 2 = Monday, ..., 7 = Saturday
            event_date = semester_start_date + timedelta(
                weeks=week - 1, days=weekday % 7
            )

            # 生成开始和结束时间的 datetime 对象
            start_datetime = datetime.strptime(
                f"{event_date.strftime('%Y-%m-%d')}T{start_time}", "%Y-%m-%dT%H:%M"
            )
            end_datetime = datetime.strptime(
                f"{event_date.strftime('%Y-%m-%d')}T{end_time}", "%Y-%m-%dT%H:%M"
            )

            # Localize the datetime objects to the specified timezone
            start_datetime = timezone.localize(start_datetime)
            end_datetime = timezone.localize(end_datetime)

            # 创建 ics 事件
            event = f"""BEGIN:VEVENT
SUMMARY:{course_name} ({teacher})
LOCATION:{location}
DTSTART;TZID=Asia/Shanghai:{start_datetime.strftime('%Y%m%dT%H%M%S')}
DTEND;TZID=Asia/Shanghai:{end_datetime.strftime('%Y%m%dT%H%M%S')}
DESCRIPTION:教师: {teacher}
END:VEVENT"""
            events.append(event)
    return events


def generate_ics(
    json_file, semester_start_date="2025-02-23", output_file="schedule.ics"
):
    """
    从 JSON 文件生成 ICS 文件。
    """
    # 从 JSON 文件加载数据
    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # 将学期开始日期转为日期对象
    semester_start_date = datetime.strptime(semester_start_date, "%Y-%m-%d")
    events = []

    for course in json_data:
        events.extend(generate_event(course, semester_start_date))

    # 生成 ICS 文件内容
    ics_content = (
        """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
"""
        + "\n".join(events)
        + "\nEND:VCALENDAR"
    )

    # 写入 ICS 文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ics_content)
    print(f"ICS 文件已保存到 {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从课程数据生成 ICS 文件。")
    parser.add_argument(
        "json_file", type=str, help="选定课程的 JSON 文件路径。"
    )
    parser.add_argument(
        "semester_start_date",
        type=str,
        help="学期开始日期，格式为 YYYY-MM-DD。",
    )

    args = parser.parse_args()

    generate_ics(args.json_file, semester_start_date=args.semester_start_date)
