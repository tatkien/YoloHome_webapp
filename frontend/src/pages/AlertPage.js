import React, { useState } from 'react';
import { Container, Card, Button, FormCheck, Badge, Modal, Image, Alert, ListGroup } from 'react-bootstrap';

function AlertPage() {
  // === 1. KHỞI TẠO DỮ LIỆU GIẢ LẬP (MOCK DATA) ===
  const [alerts, setAlerts] = useState([
  ]);

  // === 2. CÁC TRẠNG THÁI ĐIỀU KHIỂN GIAO DIỆN (STATE) ===
  const [showDetailModal, setShowDetailModal] = useState(false); // Modal chi tiết
  const [selectedAlert, setSelectedAlert] = useState(null);      // Cảnh báo đang chọn
  const [showLightboxModal, setShowLightboxModal] = useState(false); // Xem ảnh toàn màn hình
  const [showSettingsModal, setShowSettingsModal] = useState(false); // Modal cài đặt
  const [isAlertEnabled, setIsAlertEnabled] = useState(true);        // Trạng thái hệ thống
  const [alertMethods, setAlertMethods] = useState({ email: true, phone: true, alarm: false });

  // === 3. CÁC HÀM XỬ LÝ LOGIC ===
  
  // Mở chi tiết cảnh báo và đánh dấu đã đọc
  const handleOpenDetail = (alertItem) => {
    setSelectedAlert(alertItem);
    setShowDetailModal(true);
    setAlerts(alerts.map(a => a.id === alertItem.id ? { ...a, isRead: true } : a));
  };

  // Đóng modal chi tiết
  const handleCloseDetail = () => {
    setShowDetailModal(false);
    setSelectedAlert(null);
  };

  // Xóa cảnh báo khỏi danh sách
  const handleDeleteAlert = (id) => {
    setAlerts(alerts.filter(a => a.id !== id));
    handleCloseDetail();
  };

  // Tải ảnh (Mở tab mới)
  const handleDownloadImage = (imageUrl) => {
    window.open(imageUrl, '_blank'); 
  };

  // Thay đổi phương thức thông báo
  const handleAlertMethodChange = (method) => {
    setAlertMethods({ ...alertMethods, [method]: !alertMethods[method] });
  };

  return (
    <Container className="my-5" style={{ maxWidth: '800px' }}>
      
      {/* TIÊU ĐỀ VÀ NÚT CÀI ĐẶT */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="text-dark fw-bold mb-0">Alert Inbox</h2>
          <p className="text-muted mb-0 mt-1">History of detected strangers from camera</p>
        </div>
        <Button 
            variant="light" 
            className="fw-bold px-3 py-2 rounded-pill shadow-sm border text-secondary"
            onClick={() => setShowSettingsModal(true)}
        >
          ⚙️ Settings
        </Button>
      </div>

      {/* THÔNG BÁO NẾU HỆ THỐNG ĐANG TẮT */}
      {!isAlertEnabled && (
        <Alert variant="warning" className="border-0 shadow-sm mb-4 rounded-4 d-flex align-items-center">
          <span className="fs-4 me-3">⚠️</span>
          <div>
            <strong className="d-block">System Paused</strong>
            <span className="small">Camera is not currently scanning for strangers</span>
          </div>
        </Alert>
      )}

      {/* DANH SÁCH CẢNH BÁO */}
      <div className="d-flex flex-column gap-3">
        {alerts.length === 0 ? (
          <div className="text-center text-muted p-5 bg-light rounded-4 border border-dashed">
            <div style={{ fontSize: '4rem', opacity: 0.5 }}>🛡️</div>
            <h5 className="mt-3 fw-bold">All Secure!</h5>
            <p>No strangers have been detected</p>
          </div>
        ) : (
          alerts.map((alertItem) => (
            <Card 
              key={alertItem.id} 
              className={`border-0 shadow-sm cursor-pointer transition-all ${alertItem.isRead ? 'bg-light' : 'bg-white'}`}
              style={{ borderRadius: '16px', border: alertItem.isRead ? '1px solid transparent' : '1px solid #f0f0f0' }}
              onClick={() => handleOpenDetail(alertItem)}
              onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
              onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
            >
              <Card.Body className="p-3 d-flex align-items-center">
                {/* Chấm đỏ báo tin mới */}
                <div style={{ width: '12px', display: 'flex', justifyContent: 'center', marginRight: '8px' }}>
                  {!alertItem.isRead && <div className="bg-danger rounded-circle" style={{ width: '8px', height: '8px' }}></div>}
                </div>

                {/* Ảnh xem trước */}
                <Image src={alertItem.imageUrl} style={{ height: '70px', width: '90px', objectFit: 'cover', borderRadius: '10px' }} className="shadow-xs me-3" />
                
                {/* Nội dung text */}
                <div className="flex-grow-1">
                  <div className="d-flex justify-content-between align-items-center mb-1">
                    <h6 className={`mb-0 ${alertItem.isRead ? 'text-secondary' : 'text-dark fw-bold'}`} style={{ fontSize: '1.1rem' }}>Stranger Detected</h6>
                    <span className="text-muted small">{alertItem.date}</span>
                  </div>
                  <div className="d-flex align-items-center mt-2">
                    <Badge bg="light" text="secondary" className="border px-2 py-1 fw-normal rounded-2 me-2">🕒 {alertItem.time}</Badge>
                    {!alertItem.isRead && <Badge bg="danger" className="px-2 py-1 fw-normal rounded-2 bg-opacity-75">New</Badge>}
                  </div>
                </div>
              </Card.Body>
            </Card>
          ))
        )}
      </div>

      {/* MODAL 1: CHI TIẾT CẢNH BÁO */}
      <Modal show={showDetailModal} onHide={handleCloseDetail} centered size="md">
        <Modal.Header closeButton className="bg-white border-bottom-0 pb-0">
          <Modal.Title className="fw-bold fs-5 text-dark">Camera Snapshot</Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-4 pt-2">
          {selectedAlert && (
            <div className="position-relative mb-4 text-center">
              <Image src={selectedAlert.imageUrl} fluid className="rounded-4 shadow-sm border" style={{ width: '100%', maxHeight: '350px', objectFit: 'cover', cursor: 'zoom-in' }} onClick={() => setShowLightboxModal(true)} />
              <Badge bg="danger" className="position-absolute top-0 start-0 m-3 px-3 py-2 rounded-pill shadow">⚠️ Stranger</Badge>
              <div className="text-muted small mt-2">Click image to view full screen</div>
            </div>
          )}
          <div className="d-flex justify-content-center gap-3 mb-4">
            <div className="bg-light px-3 py-2 rounded-3 border w-50 text-center">
              <div className="small text-muted mb-1">Date</div>
              <strong className="text-dark">{selectedAlert?.date}</strong>
            </div>
            <div className="bg-light px-3 py-2 rounded-3 border w-50 text-center">
              <div className="small text-muted mb-1">Time</div>
              <strong className="text-dark">{selectedAlert?.time}</strong>
            </div>
          </div>
          <div className="d-flex justify-content-between gap-3">
              <Button variant="light" className="text-danger fw-bold flex-grow-1 py-2 border rounded-pill" onClick={() => handleDeleteAlert(selectedAlert.id)}>🗑️ Delete Log</Button>
              <Button variant="outline-dark" className="fw-bold px-4 py-2 rounded-pill shadow-xs" onClick={() => handleDownloadImage(selectedAlert.imageUrl)}>📥 Download</Button>
          </div>
        </Modal.Body>
      </Modal>

      {/* MODAL 2: XEM ẢNH LỚN (LIGHTBOX) */}
      <Modal show={showLightboxModal} onHide={() => setShowLightboxModal(false)} centered size="lg" contentClassName="bg-transparent border-0 shadow-none">
        <Modal.Body className="p-0 text-center position-relative d-flex justify-content-center">
          {selectedAlert && (
            <div className="position-relative d-inline-block">
              <Button variant="dark" className="position-absolute rounded-circle shadow-lg d-flex align-items-center justify-content-center" style={{ top: '-15px', right: '-15px', zIndex: 1050, width: '40px', height: '40px', border: '2px solid white' }} onClick={() => setShowLightboxModal(false)}>✕</Button>
              <Image src={selectedAlert.imageUrl} className="shadow-lg rounded-4" style={{ maxHeight: '85vh', maxWidth: '100%', objectFit: 'contain', border: '4px solid white', backgroundColor: '#000' }} />
            </div>
          )}
        </Modal.Body>
      </Modal>

      {/* MODAL 3: CÀI ĐẶT */}
      <Modal show={showSettingsModal} onHide={() => setShowSettingsModal(false)} centered>
        <Modal.Header closeButton className="border-bottom pb-3">
          <Modal.Title className="fw-bold text-dark fs-5">⚙️ Alert Settings</Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-0 bg-light">
          <div className="p-3">
            <div className="small fw-bold text-muted text-uppercase mb-2 px-2">Camera System</div>
            <ListGroup className="shadow-sm rounded-4">
              <ListGroup.Item className="d-flex justify-content-between align-items-center py-3 border-0">
                <div>
                  <div className="fw-bold text-dark">Stranger Detection</div>
                  <div className="small text-muted">Activate AI face recognition</div>
                </div>
                <FormCheck type="switch" checked={isAlertEnabled} onChange={() => setIsAlertEnabled(!isAlertEnabled)} style={{ transform: 'scale(1.2)' }} />
              </ListGroup.Item>
            </ListGroup>
          </div>
          <div className="p-3 pt-0">
            <div className="small fw-bold text-muted text-uppercase mb-2 px-2">Notification Methods</div>
            <ListGroup className="shadow-sm rounded-4">
              <ListGroup.Item className="d-flex justify-content-between align-items-center py-3 border-bottom">
                <div className="text-dark fw-medium">Email Notification</div>
                <FormCheck type="checkbox" checked={alertMethods.email} onChange={() => handleAlertMethodChange('email')} />
              </ListGroup.Item>
              <ListGroup.Item className="d-flex justify-content-between align-items-center py-3 border-bottom">
                <div className="text-dark fw-medium">Push Notification (App)</div>
                <FormCheck type="checkbox" checked={alertMethods.phone} onChange={() => handleAlertMethodChange('phone')} />
              </ListGroup.Item>
              <ListGroup.Item className="d-flex justify-content-between align-items-center py-3 border-0">
                <div className="text-danger fw-bold">Activate Local Siren</div>
                <FormCheck type="checkbox" checked={alertMethods.alarm} onChange={() => handleAlertMethodChange('alarm')} />
              </ListGroup.Item>
            </ListGroup>
          </div>
        </Modal.Body>
        <Modal.Footer className="border-0 bg-light pt-0">
          <Button variant="dark" className="w-100 rounded-pill py-2 fw-bold" onClick={() => setShowSettingsModal(false)}>Done</Button>
        </Modal.Footer>
      </Modal>

    </Container>
  );
}

export default AlertPage;