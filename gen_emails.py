import os
import win32com.client
from common import Reports, Jobs
from jenkins_export import get_latest_report, get_report_link
from jira_export import get_issues
from datetime import timedelta, datetime
import lxml.html as lh
from copy import deepcopy
import urllib

reports_titles = {
    Reports.PUBG: "PUBG Report",
    Reports.Dota2_DX11: "Dota 2 DX11 Report",
    Reports.Dota2_Vulkan: "Dota 2 Vulkan Report",
    Reports.LoL: "League of Legends Report",
    Reports.Heaven_Benchmark_DX9: "Heaven Benchmark DX9 Report",
    Reports.Valley_Benchmark_DX9: "Valley Benchmark DX9 Report",
    Reports.Heaven_Benchmark_DX11: "Heaven Benchmark DX11 Report",
    Reports.Valley_Benchmark_DX11: "Valley Benchmark DX11 Report",
    Reports.Heaven_Benchmark_OpenGL: "Heaven Benchmark OpenGL Report",
    Reports.Valley_Benchmark_OpenGL: "Valley Benchmark OpenGL Report",
}

jobs_titles = {
    Jobs.Full_Samples: "Full Samples Streaming SDK autotests",
    Jobs.Win_Full: "Remote Samples Streaming SDK autotests",
    Jobs.Ubuntu_Full: "Remote Samples Streaming SDK autotests",
    Jobs.Android_Full: "Remote Samples Streaming SDK autotests",
    Jobs.AMD_Full: "Remote Samples Streaming SDK autotests",
}

LETTER2_HTML_TABLE = "ISSUES_TABLE"

RECIPIENTS_TO = os.getenv("STREAMING_SDK_EMAIL_RECIPIENTS_TO", "")
RECIPIENTS_CC = os.getenv("STREAMING_SDK_EMAIL_RECIPIENTS_CC", "")


def load_xml(file_path: str):
    tree = None
    with open(file_path, "r") as file:
        tree = lh.parse(file)

    return tree


def write_xml(tree, file_path: str):
    tree.write(file_path, xml_declaration=True, encoding="ascii")


def append_row_to_summary_table(
    tbody: lh.Element, report_type: Reports, report: dict, row_template: lh.Element
):
    # append new row
    row = deepcopy(row_template)
    tbody.append(row)

    columns = row.findall("./td")

    columns[0].find("./p/span/a").set("href", report["url"])
    columns[0].find("./p/span/a/span").text = reports_titles[report_type]

    columns[1].find("./p/span").text = str(
        report["total"] - report["skipped"] - report["observed"]
    )
    columns[2].find("./p/span").text = str(report["passed"])
    columns[3].find("./p/span").text = str(report["failed"])
    columns[4].find("./p/span").text = str(report["error"])

    timestamp = []
    h, m, s = [
        int(x) for x in str(timedelta(seconds=int(report["execution_time"]))).split(":")
    ]
    if h > 0:
        timestamp.append("{}h".format(int(h)))
    timestamp.append("{}m".format(int(m)))
    timestamp.append("{}s".format(int(s)))

    columns[5].find("./p/span").text = " ".join(timestamp)


def generate_first_letter(recipients_to: str = "", recipients_cc: str = ""):
    html = load_xml("letters_templates/Letter1.html")

    tables_insertion_position = html.find("//div[@id='TABLES_PLACEHOLDER']")
    parent_elem = tables_insertion_position.getparent()
    insertion_index = parent_elem.index(tables_insertion_position)

    for job in [
        Jobs.Full_Samples,
        Jobs.Win_Full,
        Jobs.Android_Full,
        Jobs.Ubuntu_Full,
        Jobs.AMD_Full,
    ]:
        # collects info from json reports into dict
        reports_data: dict[str, dict[Reports, dict[str, str]]] = {}

        for report in Reports:
            if report is Reports.summary:
                continue

            since_date = (
                datetime.today() - timedelta(weeks=1) + timedelta(days=1)
            ).replace(hour=0, minute=0, second=0, microsecond=0)

            latest_report = get_latest_report(job, report, newer_than=since_date)

            if latest_report is None:
                continue

            report_url = get_report_link(
                job, latest_report["version"], report, json=False
            )

            json_report = latest_report["report"]

            for machine_name in json_report:
                if reports_data.get(machine_name) is None:
                    reports_data[machine_name] = {}

                reports_data[machine_name][report] = json_report[machine_name][
                    "summary"
                ]

                reports_data[machine_name][report]["url"] = (
                    report_url + "#" + urllib.parse.quote(machine_name)
                )

        # fill html letter template
        for machine_name in reports_data:
            table_section = load_xml("letters_templates/report_table.html")

            title_element = table_section.find("//p/span")
            title_element.text = "{report_name}, server — {server_name}, client 1 — RX 6700XT Win 10 (64bit), client 2 — RX 6700XT Win 10 (64bit):".format(
                report_name=jobs_titles[job],
                server_name=machine_name.replace("AMD Radeon ", ""),
            )

            table = table_section.find("//table")

            tbody = table.find("./tbody")

            # copy teplate row and remove it from table
            row = tbody.findall("./tr")[1]
            row_template = deepcopy(row)
            tbody.remove(row)

            for report in reports_data[machine_name]:
                append_row_to_summary_table(
                    tbody=tbody,
                    report_type=report,
                    report=reports_data[machine_name][report],
                    row_template=row_template,
                )

            for element in table_section.find("//body"):
                insertion_index += 1
                parent_elem.insert(insertion_index, element)

            for _ in range(len(reports_data[machine_name])):
                insertion_index += 1
                enter_element = lh.fromstring(
                    """
                    <p class="MsoNormal">
                        <span style="font-size: 9pt; font-family: 'Open Sans', sans-serif">
                            <o:p>&nbsp;</o:p>
                        </span>
                    </p>
                    """
                )
                parent_elem.insert(insertion_index, enter_element)

    dir = os.getcwd()
    html_file = os.path.join(dir, "Letter_1.html")
    write_xml(html, html_file)

    oft_file = os.path.join(dir, "Letter_1.oft")
    html2oft(
        html_file,
        oft_file,
        message_subject="Streaming SDK Report",
        recipients_to=recipients_to,
        recipients_cc=recipients_cc,
    )


def generate_second_letter(
    report_date: datetime, recipients_to: str = "", recipients_cc: str = ""
):
    html = load_xml("letters_templates/Letter2.html")

    table = html.find("//table[@id='{id}']".format(id=LETTER2_HTML_TABLE))
    tbody = table.find("./tbody")
    row = tbody.findall("./tr")[0]

    # copy row and remove it from table
    row_template = deepcopy(row)
    tbody.remove(row)

    issues = get_issues()
    for issue in issues:
        # append new row
        row = deepcopy(row_template)
        tbody.append(row)

        columns = row.findall("./td")

        columns[0].find("./p/span/a").set("href", issue.url)
        columns[0].find("./p/span/a/span").text = issue.key
        columns[1].find("./p/span").text = issue.summary

        columns[2].find("./p/span").text = issue.created_at
        if datetime.strptime(issue.created_at, "%d/%b/%y").year == 2021:
            span = columns[2].find("./p/span")
            span.attrib["style"] = span.attrib["style"].replace(
                "color:black", "color:#C00000"
            )

        columns[3].find("./p/span").text = issue.severity
        if issue.severity.lower() in ["blocker", "critical"]:
            span = columns[3].find("./p/span")
            span.attrib["style"] = span.attrib["style"].replace(
                "color:black", "color:#C00000"
            )

    dir = os.getcwd()
    html_file = os.path.join(dir, "Letter_2.html")
    write_xml(html, html_file)

    oft_file = os.path.join(dir, "Letter_2.oft")
    html2oft(
        html_file,
        oft_file,
        message_subject="Weekly QA Report " + report_date.strftime("%d-%b-%Y"),
        recipients_to=recipients_to,
        recipients_cc=recipients_cc,
    )


def html2oft(
    html_file_path: str,
    otf_file_path: str,
    recipients_to: str = "",
    recipients_cc: str = "",
    message_subject: str = "",
):
    olMailItem = 0x0
    obj = win32com.client.Dispatch("Outlook.Application")

    msg = obj.CreateItem(olMailItem)
    msg.Subject = message_subject
    msg.To = recipients_to
    msg.Cc = recipients_cc
    # olFormatHTML https://msdn.microsoft.com/en-us/library/office/aa219371(v=office.11).aspx
    msg.BodyFormat = 2
    msg.HTMLBody = open(html_file_path).read()
    # newMail.display()
    save_format = 2  # olTemplate	2	Microsoft Outlook template (.oft)
    msg.SaveAs(otf_file_path, save_format)


if __name__ == "__main__":
    report_date = datetime.today()
    generate_first_letter(recipients_to=RECIPIENTS_TO, recipients_cc=RECIPIENTS_CC)
    generate_second_letter(
        recipients_to=RECIPIENTS_TO,
        recipients_cc=RECIPIENTS_CC,
        report_date=report_date,
    )