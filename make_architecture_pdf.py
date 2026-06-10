from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import Flowable
import os

W, H = letter

# ── Colors ──────────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#0b0f1a")
DARK_BLUE  = colors.HexColor("#0d1b2e")
MID_BLUE   = colors.HexColor("#1a3a5c")
ACCENT     = colors.HexColor("#4a9ede")
TEXT_LIGHT = colors.HexColor("#c0d8ee")
TEXT_DIM   = colors.HexColor("#5a8aaa")
WHITE      = colors.white
GREEN      = colors.HexColor("#10b981")

# ── Styles ───────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()
title_style   = ParagraphStyle("title",    fontName="Helvetica-Bold", fontSize=28, textColor=WHITE,      alignment=TA_CENTER, spaceAfter=4)
subtitle_style= ParagraphStyle("subtitle", fontName="Helvetica",      fontSize=13, textColor=ACCENT,     alignment=TA_CENTER, spaceAfter=4)
tagline_style = ParagraphStyle("tagline",  fontName="Helvetica",      fontSize=10, textColor=TEXT_DIM,   alignment=TA_CENTER, spaceAfter=20)
section_style = ParagraphStyle("section",  fontName="Helvetica-Bold", fontSize=14, textColor=ACCENT,     spaceBefore=18, spaceAfter=8)
body_style    = ParagraphStyle("body",     fontName="Helvetica",      fontSize=10, textColor=TEXT_LIGHT,  leading=16, spaceAfter=6)
small_style   = ParagraphStyle("small",    fontName="Helvetica",      fontSize=9,  textColor=TEXT_DIM,   leading=14)
bold_style    = ParagraphStyle("bold",     fontName="Helvetica-Bold", fontSize=10, textColor=WHITE,      leading=15)


class FlowDiagram(Flowable):
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.height = 90

    def draw(self):
        c = self.canv
        boxes = [
            ("Data", "RMP +\nColl. Conf."),
            ("ES", "Elasticsearch\nServerless"),
            ("MCP", "Elastic MCP\nServer"),
            ("AI", "Gemini 2.5\nFlash"),
            ("UI", "User\nAnswer"),
        ]
        n = len(boxes)
        box_w = 88
        box_h = 54
        gap = (self.width - n * box_w) / (n - 1)
        y = (self.height - box_h) / 2

        for i, (tag, label) in enumerate(boxes):
            x = i * (box_w + gap)
            c.setFillColor(MID_BLUE)
            c.roundRect(x, y, box_w, box_h, 6, fill=1, stroke=0)
            c.setStrokeColor(ACCENT)
            c.setLineWidth(1.2)
            c.roundRect(x, y, box_w, box_h, 6, fill=0, stroke=1)
            c.setFont("Helvetica-Bold", 13)
            c.setFillColor(ACCENT)
            c.drawCentredString(x + box_w/2, y + box_h - 22, tag)
            c.setFont("Helvetica", 7.5)
            c.setFillColor(TEXT_LIGHT)
            for j, line in enumerate(label.split("\n")):
                c.drawCentredString(x + box_w/2, y + 14 - j*11, line)
            if i < n - 1:
                ax = x + box_w + 4
                ay = y + box_h / 2
                c.setStrokeColor(ACCENT)
                c.setLineWidth(1.5)
                c.line(ax, ay, ax + gap - 8, ay)
                c.setFillColor(ACCENT)
                from reportlab.graphics.shapes import Polygon
                p = c.beginPath()
                p.moveTo(ax+gap-8, ay)
                p.lineTo(ax+gap-14, ay+4)
                p.lineTo(ax+gap-14, ay-4)
                p.close()
                c.drawPath(p, fill=1, stroke=0)

    def wrap(self, *args):
        return self.width, self.height


def make_table(rows, col_widths):
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  MID_BLUE),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",       (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [DARK_BLUE, colors.HexColor("#0f1e30")]),
        ("GRID",           (0, 0), (-1, -1), 0.5, colors.HexColor("#1a3050")),
        ("TEXTCOLOR",      (0, 1), (0, -1),  ACCENT),
        ("TEXTCOLOR",      (1, 0), (-1, -1), TEXT_LIGHT),
        ("TOPPADDING",     (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 7),
        ("LEFTPADDING",    (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 10),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME",       (0, 1), (0, -1),  "Helvetica-Bold"),
    ]))
    return t


def header_canvas(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, H - 6, W, 6, fill=1, stroke=0)
    canvas.setFillColor(MID_BLUE)
    canvas.rect(0, 0, W, 28, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_DIM)
    canvas.drawString(0.75*inch, 9, "CampusVoice — Tech Stack & Architecture")
    canvas.drawRightString(W - 0.75*inch, 9, "Google Cloud Rapid Agent Hackathon 2026")
    canvas.restoreState()


os.makedirs("static", exist_ok=True)
output_path = "static/architecture.pdf"

doc = SimpleDocTemplate(output_path, pagesize=letter,
    leftMargin=0.75*inch, rightMargin=0.75*inch,
    topMargin=0.75*inch, bottomMargin=0.5*inch,
    title="CampusVoice — Tech Stack & Architecture",
    author="Vi (Srividya Narayanan)",
    subject="Google Cloud Rapid Agent Hackathon 2026")

story = []

story.append(Spacer(1, 0.3*inch))
story.append(Paragraph("CampusVoice", title_style))
story.append(Paragraph("Tech Stack &amp; Architecture", subtitle_style))
story.append(Paragraph("AI-powered student sentiment agent | Google Cloud Rapid Agent Hackathon 2026", tagline_style))
story.append(HRFlowable(width="100%", thickness=1, color=MID_BLUE, spaceAfter=16))

story.append(Paragraph("What It Does", section_style))
story.append(Paragraph(
    "CampusVoice lets students, counselors, and administrators ask plain-English questions about "
    "university professors and courses — and get synthesized answers with real quotes drawn from "
    "<b>13,192 student reviews</b> — 6,773 from Rate My Professors and 6,419 from College Confidential — "
    "across 7 US universities.",
    body_style))

story.append(Paragraph("Data Flow Pipeline", section_style))
story.append(FlowDiagram(doc.width))
story.append(Spacer(1, 12))
story.append(Paragraph(
    "A user question triggers Gemini 2.5 Flash, which calls the Elastic MCP Server as a tool. "
    "The MCP server queries Elasticsearch and returns matching reviews. Gemini synthesizes a "
    "final answer with verbatim quotes — all in a single agentic loop.",
    small_style))

story.append(Paragraph("Tech Stack", section_style))
story.append(make_table([
    ["Layer",            "Technology"],
    ["LLM",              "Google Gemini 2.5 Flash — reasoning, search planning, answer synthesis"],
    ["Search & Storage", "Elasticsearch Serverless on Elastic Cloud — vector + keyword search"],
    ["Tool Layer",       "@elastic/mcp-server-elasticsearch — MCP server over stdio JSON-RPC"],
    ["Agent Framework",  "Custom Python agent loop with Gemini function calling (no LangChain)"],
    ["Web Framework",    "Flask + Gunicorn — REST API serving the HTML/JS frontend"],
    ["Deployment",       "Google Cloud Run — containerized, auto-scales to zero, 120s timeout"],
    ["CI/CD",            "Google Cloud Build — auto-deploys from GitHub main on every push"],
    ["Data Collection",  "Rate My Professors (GraphQL API) + College Confidential (Discourse API) — 13,192 total"],
    ["Container",        "Docker — Python 3.11-slim + Node.js 20 + Elastic MCP server bundled"],
], [1.8*inch, 4.5*inch]))

story.append(Paragraph("Agent Loop (per request)", section_style))
story.append(make_table([
    ["Step",          "What happens"],
    ["1. Receive",    "Flask receives POST /api/ask with question + optional school filter"],
    ["2. Prompt",     "Gemini receives question + full search strategy in system prompt"],
    ["3. Tool call",  "Gemini generates an Elasticsearch query via function calling"],
    ["4. Execute",    "MCPClient sends tools/call to the Elastic MCP subprocess over stdio"],
    ["5. Results",    "Elasticsearch returns matching reviews; MCP passes text back to Gemini"],
    ["6. Synthesize", "Gemini reads review comments, identifies patterns, quotes verbatim"],
    ["7. Respond",    "Final answer returned as JSON and rendered in the chat UI"],
], [1.3*inch, 5.0*inch]))

story.append(Paragraph("3-Tier Search Fallback", section_style))
story.append(Paragraph(
    "To ensure the agent never returns empty results, every search follows a 3-tier fallback strategy:",
    body_style))
story.append(make_table([
    ["Tier",        "Query type",                   "When used"],
    ["1 - Primary", "school_tag term + keyword",    "First attempt for every question"],
    ["2 - Fallback","school name match + keyword",  "If tier 1 returns 0 hits"],
    ["3 - Broad",   "Keyword only, no school filter","If tier 2 also returns 0 hits"],
], [1.2*inch, 2.2*inch, 2.9*inch]))

story.append(Paragraph("Universities Covered", section_style))
story.append(make_table([
    ["Tag",         "University",                          "Reviews"],
    ["utk",         "University of Tennessee Knoxville",   "~950"],
    ["vanderbilt",  "Vanderbilt University",               "~850"],
    ["gatech",      "Georgia Institute of Technology",     "~1,100"],
    ["uf",          "University of Florida",               "~1,200"],
    ["umich",       "University of Michigan",              "~1,000"],
    ["ucla",        "UCLA",                                "~850"],
    ["duke",        "Duke University",                     "~820"],
], [0.9*inch, 3.2*inch, 2.2*inch]))

story.append(HRFlowable(width="100%", thickness=1, color=MID_BLUE, spaceBefore=20, spaceAfter=10))
links_text = (
    "<b>Live:</b> https://campus-voice-agent-420887396772.us-east1.run.app  |  "
    "<b>GitHub:</b> https://github.com/srivi19/campus-voice-agent  |  "
    "<b>Devpost:</b> https://devpost.com/software/campusvoice"
)
story.append(Paragraph(links_text, small_style))

doc.build(story, onFirstPage=header_canvas, onLaterPages=header_canvas)
print(f"Created: {output_path}")
