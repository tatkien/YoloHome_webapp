import React, { useState } from 'react';
import { Container, Row, Col, Card, Button, Form, ListGroup, Modal, Stack } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';

function TimerPage() {
  const navigate = useNavigate();

  // === 1. STATE DỮ LIỆU THIẾT BỊ VÀ HẸN GIỜ ===
  const [devices] = useState([
  ]);

  const [timers, setTimers] = useState([
  ]);

  // === 2. TRẠNG THÁI MODAL VÀ FORM ===
  const [showModal, setShowModal] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [newTime, setNewTime] = useState('');
  const [newAction, setNewAction] = useState('ON');

  // === 3. HÀM XỬ LÝ ===
  
  // Mở modal cài đặt cho thiết bị cụ thể
  const handleOpenModal = (device) => {
    setSelectedDevice(device);
    setNewTime(''); 
    setNewAction('ON');
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedDevice(null);
  };

  // Thêm mốc hẹn giờ mới
  const handleAddTimer = () => {
    if (!newTime) return; 
    const newTimer = {
      id: Date.now(),
      deviceId: selectedDevice.id,
      time: newTime,
      action: newAction
    };
    setTimers([...timers, newTimer]);
    setNewTime(''); 
  };

  // Xóa mốc hẹn giờ
  const handleDeleteTimer = (timerId) => {
    setTimers(timers.filter(t => t.id !== timerId));
  };

  // GIAO DIỆN NẾU CHƯA CÓ THIẾT BỊ
  if (devices.length === 0) {
    return (
      <Container className="my-5 text-center">
        <h2 className="mb-4 text-dark fw-bold">Device Scheduling</h2>
        <Card className="shadow-sm border-0 p-5 mx-auto" style={{ maxWidth: '500px' }}>
          <div style={{ fontSize: '4rem' }} className="mb-3">🔌</div>
          <h5 className="text-muted mb-4">No devices found!</h5>
          <Button variant="primary" size="lg" className="fw-bold" onClick={() => navigate('/items')}>
            Go to Device Management
          </Button>
        </Card>
      </Container>
    );
  }

  return (
    <Container className="my-5">
      <h2 className="text-center mb-5 text-dark fw-bold">Device Scheduling</h2>
      
      {/* LƯỚI THIẾT BỊ (2 CỘT) */}
      <Row xs={1} md={2} className="g-3">
        {devices.map((device) => {
          // Lọc lịch hẹn của từng thiết bị
          const deviceTimers = timers
            .filter(t => t.deviceId === device.id)
            .sort((a, b) => a.time.localeCompare(b.time));
          
          return (
            <Col key={device.id}>
              <Card 
                className="h-100 shadow border-0 hover-shadow cursor-pointer p-3"
                style={{ cursor: 'pointer', transition: 'transform 0.2s', borderRadius: '12px' }}
                onClick={() => handleOpenModal(device)}
                onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
                onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
              >
                <Card.Body className="p-3 d-flex flex-column">
                  <div className="d-flex align-items-center mb-3">
                    <div style={{ fontSize: '2rem' }} className="me-3 p-2 bg-light rounded-circle shadow-xs">{device.icon}</div>
                    <Card.Title className="fw-bold fs-5 m-0 text-dark">{device.name}</Card.Title>
                  </div>
                  
                  <div className="mt-2 flex-grow-1">
                    <h6 className="text-dark fw-bold mb-3 fs-6">Schedules:</h6>
                    {deviceTimers.length > 0 ? (
                      <Stack direction="horizontal" gap={3} className="flex-wrap">
                        {deviceTimers.map((timer) => (
                          <div key={timer.id} className="d-flex align-items-center bg-white border rounded shadow-xs p-2" style={{ minWidth: '110px', border: '1px solid #ddd', backgroundColor: '#fafafa' }}>
                            <div className="fs-6 fw-bold text-dark me-2">{timer.time}</div>
                            <div className={timer.action === 'ON' ? 'text-success fw-bold' : 'text-danger fw-bold'} style={{ fontSize: '0.9rem' }}>
                              {timer.action}
                            </div>
                          </div>
                        ))}
                      </Stack>
                    ) : (
                      <div className="d-flex align-items-center bg-white border rounded shadow-xs p-2" style={{ border: '1px solid #ddd', backgroundColor: '#fafafa' }}>
                        <span className="fs-6 me-2">🚫</span> No active schedules
                      </div>
                    )}
                  </div>
                </Card.Body>
              </Card>
            </Col>
          );
        })}
      </Row>

      {/* MODAL CÀI ĐẶT HẸN GIỜ */}
      <Modal show={showModal} onHide={handleCloseModal} centered size="lg">
        <Modal.Header closeButton className="bg-light border-0">
          <Modal.Title className="fw-bold fs-5">Settings: {selectedDevice?.name}</Modal.Title>
        </Modal.Header>
        <Modal.Body className="p-4">
          {/* FORM THÊM MỚI */}
          <Form className="mb-5 p-4 bg-light rounded border shadow-xs">
            <h6 className="fw-bold mb-3">Add New Time Slot</h6>
            <Row className="g-3">
              <Col xs={7}>
                <Form.Group>
                  <Form.Control type="time" value={newTime} onChange={(e) => setNewTime(e.target.value)} className="form-control-lg" />
                </Form.Group>
              </Col>
              <Col xs={5}>
                <Form.Group>
                  <Form.Select value={newAction} onChange={(e) => setNewAction(e.target.value)} className="form-select-lg">
                    <option value="ON">ON</option>
                    <option value="OFF">OFF</option>
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>
            <Button variant="primary" className="w-100 mt-3 fw-bold lg" onClick={handleAddTimer} disabled={!newTime}>
              + Add Timer
            </Button>
          </Form>

          {/* DANH SÁCH LỊCH ĐÃ CÀI ĐẶT TRONG MODAL */}
          <h6 className="fw-bold text-dark mb-3 fs-6">Configured for {selectedDevice?.name}</h6>
          {timers.filter(t => t.deviceId === selectedDevice?.id).length === 0 ? (
            <div className="text-center text-muted p-4 border rounded bg-white fs-6 shadow-xs">No active timers.</div>
          ) : (
            <ListGroup variant="flush">
              {timers
                .filter(t => t.deviceId === selectedDevice?.id)
                .sort((a, b) => a.time.localeCompare(b.time))
                .map((timer) => (
                    <ListGroup.Item key={timer.id} className="d-flex justify-content-between align-items-center bg-white border rounded shadow-xs mb-3 p-3 fs-6">
                      <div>
                        Set to <strong className={timer.action === 'ON' ? 'text-success' : 'text-danger'}>{timer.action}</strong> at <span className="fw-bold">{timer.time}</span>
                      </div>
                      <Button variant="outline-danger" size="sm" onClick={() => handleDeleteTimer(timer.id)}>Delete</Button>
                    </ListGroup.Item>
              ))}
            </ListGroup>
          )}
        </Modal.Body>
      </Modal>

    </Container>
  );
}

export default TimerPage;