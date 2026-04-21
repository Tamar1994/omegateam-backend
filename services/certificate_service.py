"""
Certificate Generation Service for Omega Team
Generates PDF certificates of participation for athletes
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor
import os

class CertificateService:
    """Service to generate athlete participation certificates"""
    
    # Colors for certificate
    COLOR_GOLD = HexColor("#FFD700")
    COLOR_DARK = HexColor("#1a1a1a")
    COLOR_WHITE = HexColor("#FFFFFF")
    COLOR_ACCENT = HexColor("#C41E3A")  # Red accent
    
    @staticmethod
    def gerar_certificado_participacao(
        atleta_nome: str,
        atleta_email: str,
        campeonato_nome: str,
        data_evento: datetime,
        categoria: str,
        modalidade: str,
        medalha: str = "participacao"
    ) -> BytesIO:
        """
        Generate a participation certificate for an athlete
        
        Args:
            atleta_nome: Athlete's name
            atleta_email: Athlete's email
            campeonato_nome: Tournament/Championship name
            data_evento: Event date
            categoria: Category (weight class or age group)
            modalidade: Modality (Kyorugui or Poomsae)
            medalha: Medal earned (ouro, prata, bronze, participacao)
        
        Returns:
            BytesIO object with PDF content
        """
        
        # Create PDF in landscape A4 format
        buffer = BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=landscape(A4))
        width, height = landscape(A4)
        
        # Background - Gradient effect with rectangles
        pdf_canvas.setFillColor(CertificateService.COLOR_DARK)
        pdf_canvas.rect(0, 0, width, height, fill=1, stroke=0)
        
        # Top accent bar
        pdf_canvas.setFillColor(CertificateService.COLOR_ACCENT)
        pdf_canvas.rect(0, height - 80, width, 80, fill=1, stroke=0)
        
        # Bottom accent bar with medal color
        medal_color = CertificateService._get_medal_color(medalha)
        pdf_canvas.setFillColor(medal_color)
        pdf_canvas.rect(0, 0, width, 60, fill=1, stroke=0)
        
        # Title section
        pdf_canvas.setFont("Helvetica-Bold", 28)
        pdf_canvas.setFillColor(CertificateService.COLOR_GOLD)
        pdf_canvas.drawString(width / 2 - 150, height - 45, "🥋 CERTIFICADO DE PARTICIPAÇÃO")
        
        # Omega Team branding
        pdf_canvas.setFont("Helvetica", 12)
        pdf_canvas.setFillColor(HexColor("#CCCCCC"))
        pdf_canvas.drawString(width / 2 - 80, height - 70, "OMEGA TEAM - Campeonato de Taekwondo")
        
        # Main content
        pdf_canvas.setFillColor(CertificateService.COLOR_WHITE)
        
        # Certificate border - elegant frame
        pdf_canvas.setLineWidth(2)
        pdf_canvas.setStrokeColor(medal_color)
        pdf_canvas.rect(40, 80, width - 80, height - 160, fill=0, stroke=1)
        
        # Certificate text content
        y_position = height - 160
        
        # "Certificamos que:" text
        pdf_canvas.setFont("Helvetica-Bold", 16)
        pdf_canvas.drawString(width / 2 - 60, y_position, "Certificamos que:")
        
        # Athlete name (prominent)
        y_position -= 40
        pdf_canvas.setFont("Helvetica-Bold", 24)
        pdf_canvas.setFillColor(medal_color)
        # Split long names if needed
        if len(atleta_nome) > 40:
            first_part = atleta_nome[:40]
            second_part = atleta_nome[40:]
            pdf_canvas.drawString(width / 2 - 150, y_position, first_part)
            y_position -= 30
            pdf_canvas.drawString(width / 2 - len(second_part) * 6, y_position, second_part)
        else:
            pdf_canvas.drawString(width / 2 - len(atleta_nome) * 7, y_position, atleta_nome)
        
        # Details section
        y_position -= 50
        pdf_canvas.setFont("Helvetica", 12)
        pdf_canvas.setFillColor(CertificateService.COLOR_WHITE)
        
        details = [
            f"Participou do Campeonato: {campeonato_nome}",
            f"Data do Evento: {data_evento.strftime('%d de %B de %Y').replace('January', 'Janeiro').replace('February', 'Fevereiro').replace('March', 'Março').replace('April', 'Abril').replace('May', 'Maio').replace('June', 'Junho').replace('July', 'Julho').replace('August', 'Agosto').replace('September', 'Setembro').replace('October', 'Outubro').replace('November', 'Novembro').replace('December', 'Dezembro')}",
            f"Categoria: {categoria}",
            f"Modalidade: {modalidade}",
        ]
        
        for detail in details:
            pdf_canvas.drawString(100, y_position, detail)
            y_position -= 25
        
        # Medal section
        y_position -= 10
        pdf_canvas.setFont("Helvetica-Bold", 14)
        pdf_canvas.setFillColor(medal_color)
        
        medal_emoji = CertificateService._get_medal_emoji(medalha)
        medal_text = CertificateService._get_medal_text(medalha)
        pdf_canvas.drawString(width / 2 - 80, y_position, f"{medal_emoji} {medal_text}")
        
        # Footer with timestamp
        y_position = 35
        pdf_canvas.setFont("Helvetica", 10)
        pdf_canvas.setFillColor(HexColor("#999999"))
        pdf_canvas.drawString(100, y_position, f"Emitido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        pdf_canvas.drawString(width - 200, y_position, f"Email: {atleta_email}")
        
        # Signature area (decorative)
        y_position = 120
        pdf_canvas.setLineWidth(1)
        pdf_canvas.setStrokeColor(HexColor("#666666"))
        pdf_canvas.line(width - 300, y_position - 40, width - 100, y_position - 40)
        pdf_canvas.setFont("Helvetica", 10)
        pdf_canvas.setFillColor(HexColor("#CCCCCC"))
        pdf_canvas.drawString(width - 250, y_position - 50, "Assinado Digitalmente")
        
        # Save PDF to buffer
        pdf_canvas.save()
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def _get_medal_color(medalha: str):
        """Get color for medal type"""
        colors = {
            "ouro": HexColor("#FFD700"),
            "prata": HexColor("#C0C0C0"),
            "bronze": HexColor("#CD7F32"),
            "participacao": HexColor("#4169E1")
        }
        return colors.get(medalha, colors["participacao"])
    
    @staticmethod
    def _get_medal_emoji(medalha: str) -> str:
        """Get emoji for medal type"""
        emojis = {
            "ouro": "🥇",
            "prata": "🥈",
            "bronze": "🥉",
            "participacao": "🎖️"
        }
        return emojis.get(medalha, "🎖️")
    
    @staticmethod
    def _get_medal_text(medalha: str) -> str:
        """Get text description for medal"""
        texts = {
            "ouro": "MEDALHA DE OURO",
            "prata": "MEDALHA DE PRATA",
            "bronze": "MEDALHA DE BRONZE",
            "participacao": "CERTIFICADO DE PARTICIPAÇÃO"
        }
        return texts.get(medalha, "CERTIFICADO DE PARTICIPAÇÃO")
