import React from 'react'
import {createRoot} from 'react-dom/client'
import {BrowserRouter} from 'react-router-dom'
import '@fontsource-variable/plus-jakarta-sans'
import App from './App'
import './style.css'
import './compact.css'
import './today.css'
createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><App/></BrowserRouter></React.StrictMode>)
