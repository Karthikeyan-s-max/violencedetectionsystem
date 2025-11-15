from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from ultralytics import YOLO
import cv2
import os
from datetime import datetime
import logging
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib import colors
from io import BytesIO
import traceback

logging.basicConfig(
    filename='violence_detection.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.secret_key = 'your-secret-key-2025'

# ============ DATABASE ============
USERS = {
    'user1': 'password123',
    'admin': 'admin123'
}

# ============ LOAD MODEL ============
MODEL = None

def load_model():
    global MODEL
    try:
        MODEL = YOLO('yolov8m.pt')  # Use pre-trained model
        print("Model loaded successfully!")
        return True
    except Exception as e:
        print(f"Model load error: {e}")
        MODEL = None
        return False

load_model()

# ============ LOGIN DECORATOR ============
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ============ PAGES ============
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('user_dashboard'))
    return render_template('login_screen.html')

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    return render_template('user_dashboard.html')

@app.route('/video_upload')
@login_required
def video_upload():
    return render_template('video_upload_page.html')

@app.route('/live_cctv')
@login_required
def live_cctv():
    return render_template('live_cctv_page.html')

# ============ API - LOGIN ============
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'user')
        
        if username in USERS and USERS[username] == password:
            session['user'] = username
            session['role'] = role
            logging.info(f"Login: {username}")
            return jsonify({'success': True, 'role': role}), 200
        
        logging.warning(f"Login failed: {username}")
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True}), 200

# ============ API - UPLOAD VIDEO ============
@app.route('/api/upload-video', methods=['POST'])
@login_required
def upload_video():
    try:
        print("[UPLOAD] Starting...")
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            return jsonify({'success': False, 'error': 'Invalid format'}), 400
        
        os.makedirs('static/uploads', exist_ok=True)
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join('static/uploads', filename)
        file.save(filepath)
        
        print(f"[UPLOAD] Saved: {filepath}")
        logging.info(f"File uploaded: {filename}")
        
        return jsonify({
            'success': True,
            'filepath': filepath,
            'filename': filename
        }), 200
        
    except Exception as e:
        print(f"[UPLOAD] ERROR: {e}")
        logging.error(f"Upload error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API - DETECT VIOLENCE ============
@app.route('/api/detect', methods=['POST'])
@login_required
def detect_violence():
    try:
        print("[DETECT] Starting detection...")
        data = request.json
        filepath = data.get('filepath')
        threshold = float(data.get('threshold', 0.5))
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        if not MODEL:
            return jsonify({'success': False, 'error': 'Model not loaded'}), 500
        
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            return jsonify({'success': False, 'error': 'Cannot open video'}), 400
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = 0
        violence_count = 0
        detections = []
        
        best_frame = None
        best_confidence = 0.0
        best_timestamp = "00:00"
        
        print(f"[DETECT] Total frames: {total_frames}, FPS: {fps}")
        
        frame_num = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            frame_num += 1
            
            if frame_count % 5 != 0:
                continue
            
            if frame_num % 50 == 0:
                print(f"[DETECT] Processing frame {frame_count}/{total_frames}")
            
            try:
                results = MODEL(frame, verbose=False, conf=threshold)
                
                for r in results:
                    for box in r.boxes:
                        try:
                            conf = float(box.conf[0]) if hasattr(box.conf, '__len__') else float(box.conf)
                            cls = int(box.cls[0]) if hasattr(box.cls, '__len__') else int(box.cls)
                            
                            if cls == 0 and conf >= threshold:
                                violence_count += 1
                                timestamp = frame_count / fps if fps > 0 else 0
                                
                                if conf > best_confidence:
                                    best_confidence = conf
                                    best_frame = frame.copy()
                                    best_timestamp = f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}"
                                    print(f"[DETECT] New best frame: {best_timestamp} ({conf*100:.1f}%)")
                                
                                detections.append({
                                    'frame': frame_count,
                                    'timestamp': best_timestamp,
                                    'confidence': float(conf)
                                })
                        except:
                            continue
            except:
                continue
        
        cap.release()
        print(f"[DETECT] Violence count: {violence_count}")
        
        # SAVE BEST FRAME
        best_frame_path = None
        if best_frame is not None and violence_count > 0:
            try:
                os.makedirs('static/detections', exist_ok=True)
                timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                best_frame_path = f"static/detections/{timestamp_str}_best.jpg"
                cv2.imwrite(best_frame_path, best_frame)
                print(f"[DETECT] Best frame saved: {best_frame_path}")
            except Exception as e:
                print(f"[DETECT] Error saving frame: {e}")
        
        avg_conf = sum(d['confidence'] for d in detections) / len(detections) if detections else 0.0
        
        result_dict = {
            'success': True,
            'total_frames': total_frames,
            'violence_count': violence_count,
            'detections': detections[:5],
            'average_confidence': float(avg_conf),
            'model_used': 'yolov8',
            'best_frame': best_frame_path,
            'best_confidence': float(best_confidence),
            'best_timestamp': best_timestamp
        }
        
        print(f"[DETECT] Returning result: {result_dict}")
        logging.info(f"Detection: {violence_count} events, {avg_conf*100:.1f}% confidence")
        
        return jsonify({'results': result_dict}), 200
        
    except Exception as e:
        print(f"[DETECT] ERROR: {e}")
        traceback.print_exc()
        logging.error(f"Detection error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API - GENERATE PDF REPORT ============
@app.route('/api/generate-report', methods=['POST'])
@login_required
def generate_report():
    try:
        print("[REPORT] Generating PDF...")
        data = request.json
        
        filename = data.get('filename', 'video.mp4')
        violence_count = int(data.get('violence_count', 0))
        best_confidence = float(data.get('best_confidence', 0))
        best_timestamp = data.get('best_timestamp', '00:00')
        avg_confidence = float(data.get('avg_confidence', 0))
        best_frame_path = data.get('best_frame_path')
        
        print(f"[REPORT] Data: violence={violence_count}, conf={best_confidence}, frame={best_frame_path}")
        
        # Create PDF
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#FF4444'),
            spaceAfter=30,
            alignment=1
        )
        elements.append(Paragraph("VIOLENCE DETECTION REPORT", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Report Info
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#00CCFF'),
            spaceAfter=12
        )
        
        elements.append(Paragraph("Report Information", heading_style))
        
        info_data = [
            ['Generated Date:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Video File:', filename],
            ['Model Used:', 'YOLOv8']
        ]
        
        info_table = Table(info_data, colWidths=[2.5*inch, 3.5*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1A1A2E')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Detection Results
        elements.append(Paragraph("Detection Results", heading_style))
        
        if violence_count > 0:
            results_data = [
                ['Metric', 'Value'],
                ['Violence Events Detected', str(violence_count)],
                ['Best Confidence Score', f'{best_confidence*100:.1f}%'],
                ['Average Confidence', f'{avg_confidence*100:.1f}%'],
                ['Detection Timestamp', best_timestamp],
                ['Status', 'VIOLENCE DETECTED']
            ]
            status_color = colors.HexColor('#FF4444')
        else:
            results_data = [
                ['Metric', 'Value'],
                ['Violence Events Detected', '0'],
                ['Status', 'NO VIOLENCE DETECTED']
            ]
            status_color = colors.HexColor('#00CC00')
        
        results_table = Table(results_data, colWidths=[2.5*inch, 3.5*inch])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (-1, -1), (-1, -1), status_color)
        ]))
        elements.append(results_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Add Image
        if best_frame_path and os.path.exists(best_frame_path):
            try:
                elements.append(PageBreak())
                elements.append(Paragraph("Best Detection Frame", heading_style))
                elements.append(Spacer(1, 0.2*inch))
                img = Image(best_frame_path, width=5.5*inch, height=3.5*inch)
                elements.append(img)
                print(f"[REPORT] Image added: {best_frame_path}")
            except Exception as e:
                print(f"[REPORT] Error adding image: {e}")
        
        # Build PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        
        print("[REPORT] PDF generated successfully")
        
        # Return file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'VDS_Report_{timestamp}.pdf'
        )
        
    except Exception as e:
        print(f"[REPORT] ERROR: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ ERROR HANDLERS ============
@app.errorhandler(404)
def not_found(e):
    return render_template('login_screen.html'), 404

@app.errorhandler(500)
def server_error(e):
    print(f"Server 500: {e}")
    return jsonify({'success': False, 'error': 'Server error'}), 500

if __name__ == '__main__':
    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('static/detections', exist_ok=True)
    print("\n" + "="*60)
    print("Violence Detection System")
    print("="*60)
    print("URL: http://localhost:5000")
    print("User: user1 / password123")
    print(f"Model: {'LOADED' if MODEL else 'NOT LOADED'}")
    print("="*60 + "\n")
    app.run(debug=True, port=5000)
