import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ModelEvaluation from './ModelEvaluation'
import './styles.css'
const evaluation = new URLSearchParams(window.location.search).get('evaluation')
const page = evaluation === 'tep-detector' || evaluation === 'tep-pressure-20m' ? <ModelEvaluation kind={evaluation} /> : <App />
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode>{page}</React.StrictMode>)

