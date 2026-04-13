const express = require('express');
const cors = require('cors');
const fs = require('fs').promises;
const path = require('path');
const { spawn } = require('child_process');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// File paths
const RESUME_FILE = path.join(__dirname, 'resume.json');
const STARTUPS_FILE = path.join(__dirname, 'startups.json');
const GENERATED_EMAILS_FILE = path.join(__dirname, 'generated_emails.json');
const TRACKING_FILE = path.join(__dirname, 'email_tracking.json');

// Helper function to read JSON file
async function readJsonFile(filePath) {
    try {
        const data = await fs.readFile(filePath, 'utf-8');
        return JSON.parse(data);
    } catch (error) {
        console.error(`Error reading ${filePath}:`, error);
        return null;
    }
}

// Helper function to write JSON file
async function writeJsonFile(filePath, data) {
    try {
        await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
        return true;
    } catch (error) {
        console.error(`Error writing ${filePath}:`, error);
        return false;
    }
}

// Helper function to run Python script
function runPythonScript(scriptName, args = []) {
    return new Promise((resolve, reject) => {
        const pythonPath = process.env.PYTHON_PATH || 'python';
        const scriptPath = path.join(__dirname, scriptName);
        
        const pythonProcess = spawn(pythonPath, [scriptPath, ...args]);
        
        let stdout = '';
        let stderr = '';
        
        pythonProcess.stdout.on('data', (data) => {
            stdout += data.toString();
            console.log(`Python stdout: ${data}`);
        });
        
        pythonProcess.stderr.on('data', (data) => {
            stderr += data.toString();
            console.error(`Python stderr: ${data}`);
        });
        
        pythonProcess.on('close', (code) => {
            if (code === 0) {
                resolve({ success: true, output: stdout });
            } else {
                reject({ success: false, error: stderr, code });
            }
        });
    });
}

// ========== API Routes ==========

// Dashboard stats
app.get('/api/stats', async (req, res) => {
    try {
        const tracking = await readJsonFile(TRACKING_FILE) || { sent_emails: [], processed_companies: [] };
        const generatedEmails = await readJsonFile(GENERATED_EMAILS_FILE) || [];
        const startups = await readJsonFile(STARTUPS_FILE) || { data: [] };
        
        const stats = {
            totalStartups: startups.data?.length || 0,
            emailsGenerated: generatedEmails.length,
            emailsSent: tracking.sent_emails?.length || 0,
            emailsPending: generatedEmails.length - (tracking.sent_emails?.length || 0),
            processedCompanies: tracking.processed_companies?.length || 0
        };
        
        res.json(stats);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Resume endpoints
app.get('/api/resume', async (req, res) => {
    try {
        const resume = await readJsonFile(RESUME_FILE);
        if (!resume) {
            return res.status(404).json({ error: 'Resume not found' });
        }
        res.json(resume);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.put('/api/resume', async (req, res) => {
    try {
        const success = await writeJsonFile(RESUME_FILE, req.body);
        if (success) {
            res.json({ message: 'Resume updated successfully', data: req.body });
        } else {
            res.status(500).json({ error: 'Failed to update resume' });
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Startups endpoints
app.get('/api/startups', async (req, res) => {
    try {
        const startups = await readJsonFile(STARTUPS_FILE);
        if (!startups) {
            return res.status(404).json({ error: 'Startups file not found' });
        }
        res.json(startups);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.post('/api/startups', async (req, res) => {
    try {
        const startups = await readJsonFile(STARTUPS_FILE) || { data: [] };
        const newStartup = {
            id: Date.now(),
            ...req.body,
            added_date: new Date().toISOString()
        };
        startups.data.push(newStartup);
        
        const success = await writeJsonFile(STARTUPS_FILE, startups);
        if (success) {
            res.json({ message: 'Startup added successfully', data: newStartup });
        } else {
            res.status(500).json({ error: 'Failed to add startup' });
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.put('/api/startups/:id', async (req, res) => {
    try {
        const startups = await readJsonFile(STARTUPS_FILE);
        const index = startups.data.findIndex(s => s.id === parseInt(req.params.id));
        
        if (index === -1) {
            return res.status(404).json({ error: 'Startup not found' });
        }
        
        startups.data[index] = { ...startups.data[index], ...req.body };
        
        const success = await writeJsonFile(STARTUPS_FILE, startups);
        if (success) {
            res.json({ message: 'Startup updated successfully', data: startups.data[index] });
        } else {
            res.status(500).json({ error: 'Failed to update startup' });
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.delete('/api/startups/:id', async (req, res) => {
    try {
        const startups = await readJsonFile(STARTUPS_FILE);
        const index = startups.data.findIndex(s => s.id === parseInt(req.params.id));
        
        if (index === -1) {
            return res.status(404).json({ error: 'Startup not found' });
        }
        
        startups.data.splice(index, 1);
        
        const success = await writeJsonFile(STARTUPS_FILE, startups);
        if (success) {
            res.json({ message: 'Startup deleted successfully' });
        } else {
            res.status(500).json({ error: 'Failed to delete startup' });
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Generated emails endpoints
app.get('/api/emails', async (req, res) => {
    try {
        const emails = await readJsonFile(GENERATED_EMAILS_FILE) || [];
        res.json(emails);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.put('/api/emails/:index', async (req, res) => {
    try {
        const emails = await readJsonFile(GENERATED_EMAILS_FILE) || [];
        const index = parseInt(req.params.index);
        
        if (index < 0 || index >= emails.length) {
            return res.status(404).json({ error: 'Email not found' });
        }
        
        emails[index] = { ...emails[index], ...req.body };
        
        const success = await writeJsonFile(GENERATED_EMAILS_FILE, emails);
        if (success) {
            res.json({ message: 'Email updated successfully', data: emails[index] });
        } else {
            res.status(500).json({ error: 'Failed to update email' });
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Generate emails endpoint
app.post('/api/generate-emails', async (req, res) => {
    try {
        console.log('Starting email generation...');
        const result = await runPythonScript('generate_emails.py');
        
        if (result.success) {
            const emails = await readJsonFile(GENERATED_EMAILS_FILE) || [];
            res.json({ 
                message: 'Emails generated successfully', 
                count: emails.length,
                emails: emails 
            });
        } else {
            res.status(500).json({ error: 'Email generation failed', details: result.error });
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Send emails endpoint
app.post('/api/send-emails', async (req, res) => {
    try {
        const { indices } = req.body; // Array of email indices to send
        
        if (!indices || !Array.isArray(indices)) {
            return res.status(400).json({ error: 'Invalid request: indices array required' });
        }
        
        console.log('Sending emails...');
        // Note: You might need to modify send_emails.py to accept specific indices
        const result = await runPythonScript('send_emails.py');
        
        if (result.success) {
            res.json({ 
                message: 'Emails sent successfully',
                output: result.output 
            });
        } else {
            res.status(500).json({ error: 'Email sending failed', details: result.error });
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Tracking data endpoint
app.get('/api/tracking', async (req, res) => {
    try {
        const tracking = await readJsonFile(TRACKING_FILE) || { sent_emails: [], processed_companies: [] };
        res.json(tracking);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Start server
app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
    console.log(`Access the dashboard at http://localhost:${PORT}`);
});
