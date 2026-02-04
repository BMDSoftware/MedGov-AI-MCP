import { useState, useEffect } from 'react';
import { getApiUrl } from '../config.js';
import './PatientSelection.css';

function PatientSelection({ onPatientSelect }) {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchPatients();
  }, []);

  const fetchPatients = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(getApiUrl('/api/patients'));
      const data = await response.json();
      
      if (data.error) {
        setError(data.error);
        setPatients([]);
      } else {
        setPatients(data.patients || []);
      }
    } catch (err) {
      console.error('Error fetching patients:', err);
      setError(`Failed to load patients: ${err.message}`);
      setPatients([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredPatients = patients.filter(patient =>
    patient.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    patient.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handlePatientSelect = (patient) => {
    onPatientSelect(patient);
  };

  if (loading) {
    return (
      <div className="patient-selection">
        <div className="patient-header">
          <h2>Select a Patient</h2>
        </div>
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading patients from FHIR server...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="patient-selection">
        <div className="patient-header">
          <h2>Select a Patient</h2>
        </div>
        <div className="error-container">
          <p className="error-message">{error}</p>
          <button onClick={fetchPatients} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (patients.length === 0) {
    return (
      <div className="patient-selection">
        <div className="patient-header">
          <h2>Select a Patient</h2>
        </div>
        <div className="empty-container">
          <p>No patients found in FHIR server</p>
          <button onClick={fetchPatients} className="retry-button">
            Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="patient-selection">
      <div className="patient-header">
        <h2>Select a Patient</h2>
        <p>Choose a patient to start a healthcare conversation</p>
      </div>

      <div className="patient-search">
        <input
          type="text"
          placeholder="Search patients by name or ID..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>
      
      <div className="patients-grid">
        {filteredPatients.map((patient) => (
          <div key={patient.id} className="patient-card">
            <div className="patient-info">
              <h3 className="patient-name">{patient.name}</h3>
              <div className="patient-details">
                <span className="patient-id">ID: {patient.id}</span>
                <span className="patient-birthdate">Born: {patient.birthDate}</span>
                <span className="patient-gender">Gender: {patient.gender}</span>
              </div>
            </div>
            <button 
              className="start-conversation-btn"
              onClick={() => handlePatientSelect(patient)}
            >
              Start Healthcare Conversation
            </button>
          </div>
        ))}
      </div>

      {filteredPatients.length === 0 && (
        <div className="no-patients">
          <p>No patients found matching "{searchTerm}"</p>
        </div>
      )}
    </div>
  );
}

export default PatientSelection;