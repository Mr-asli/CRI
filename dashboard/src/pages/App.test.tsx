import { describe,it,expect,vi } from 'vitest';
import { render,screen } from '@testing-library/react';
import App from './App';
vi.mock('../api',()=>({getStatus:async()=>({connected:false,error:'offline'})}));
describe('CRI dashboard',()=>{it('shows disconnected state without fabricated metrics',async()=>{render(<App/>);expect(await screen.findByText('DISCONNECTED')).toBeTruthy();expect(screen.getByText(/No placeholder metrics/)).toBeTruthy();});it('renders all navigation areas',()=>{render(<App/>);for(const label of ['Overview','Agents','Tasks','Self-improvement','Approvals','Audit','Security','Memory','Monitoring','Settings','Kill switch'])expect(screen.getByRole('button',{name:label})).toBeTruthy();});});
