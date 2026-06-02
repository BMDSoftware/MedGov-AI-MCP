import './About.css';

function About({ onNavigate }) {
  return (
    <div className="about-root">
      <nav className="about-topnav">
        <button className="about-back" onClick={() => onNavigate('home')}>
          <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M19 12H5M12 5l-7 7 7 7"/>
          </svg>
          Back
        </button>
        <span className="about-topnav-brand">MedGov-AI</span>
      </nav>

      <div className="about-content">

        <div className="about-hero">
          <h1 className="about-title">About MedGov-AI</h1>
          <p className="about-lead">
            MedGov-AI is an agentic health integrator designed to help clinical professionals connect health data sources
            and automate complex workflows through AI. It acts as an intelligent orchestrator that integrates specialized
            health tools — from imaging analysis to terminology services and structured reporting — so that routine tasks
            are handled autonomously, freeing clinicians to focus on complex cases and direct patient care.
          </p>
        </div>

        <div className="about-grid">
          <div className="about-card">
            <div className="about-card-icon">
              <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
                <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2v-4M9 21H5a2 2 0 0 1-2-2v-4m0 0h18"/>
              </svg>
            </div>
            <h3>Clinical Workflow Automation</h3>
            <p>Upload DICOM series or pathology images and describe your goal. The agent selects tools, runs inference, and produces structured clinical reports, without manual intervention at each step.</p>
          </div>

          <div className="about-card">
            <div className="about-card-icon">
              <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
              </svg>
            </div>
            <h3>Research Support</h3>
            <p>Automate repetitive imaging analysis pipelines. Workspace monitoring detects new files and triggers the full analysis pipeline automatically, enabling large-scale research workflows without constant supervision.</p>
          </div>

          <div className="about-card">
            <div className="about-card-icon">
              <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
                <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>
              </svg>
            </div>
            <h3>Segmentation and Detection</h3>
            <p>MONAI models for volumetric organ segmentation on CT and MRI series. Cellpose v4 for cell detection and counting on pathology ROI images. Results are structured and persisted for audit and review.</p>
          </div>

          <div className="about-card">
            <div className="about-card-icon">
              <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
            </div>
            <h3>Structured Reports</h3>
            <p>RadLex/RadReport templates for radiology and pathology-specific templates for whole-slide image analysis. Reports are generated autonomously and can be reviewed and finalized by the clinician.</p>
          </div>
        </div>

        <div className="about-section">
          <h2>Consortium</h2>
          <div className="about-partners">
            <span className="about-partner">Universidade de Aveiro</span>
            <span className="about-partner-sep">·</span>
            <span className="about-partner">BMD Software</span>
          </div>
        </div>

        <div className="about-ack-section">
          <div className="about-ack-logos">
            <img
              src="https://www.healthfromportugal.pt/static/site/images/sponsors/footer-hfp.svg"
              alt="Health from Portugal"
              className="about-ack-logo"
            />
          </div>
          <p className="about-ack-text">
            This work has received support from the "Health from Portugal - Agenda Mobilizadora para a Inovação Empresarial"
            project, funded by Plano de Recuperação e Resiliência português under grant agreement No C644937233-00000047.
          </p>
        </div>

      </div>
    </div>
  );
}

export default About;
