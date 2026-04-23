import ReactDOM from 'react-dom/client';
import { ClippyProvider, AGENTS } from '@react95/clippy';
import App from './App.tsx';

import '@react95/core/GlobalStyle';
import '@react95/core/themes/win95.css';

import '../css/index.css';

import './index.css';
import { ModalProvider } from './ModalProvider.tsx';

const availableAgents = Object.keys(AGENTS);
const randomIndex = Math.ceil(Math.random() * availableAgents.length);
const agentIndex = availableAgents[randomIndex] as keyof typeof AGENTS;
const agent = AGENTS[agentIndex];

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ClippyProvider agentName={agent}>
    <ModalProvider>
      <App />
    </ModalProvider>
  </ClippyProvider>,
);
