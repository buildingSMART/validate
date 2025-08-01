import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { basename } from 'path';

const BASE_URL = 'http://localhost:8000';
const TEST_CREDENTIALS = 'root:root';

test.describe('API - ValidationRequest', () => {

    test('POST accepts valid file', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST without trailing slash accepts valid file', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST implements file size limit', async ({ request }) => {

        // try to post a large file
        const file_name = 'very_large_file.ifc';
        const largeBuffer = Buffer.alloc(300 * 1024 * 1024, 0); // 300 MB of dummy data (> 256 MB limit)
        const file = new File([largeBuffer], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 413 Payload Too Large
        expect(response.statusText()).toBe('Request Entity Too Large');
        expect(response.status()).toBe(413); 
        expect(await response.json()).toEqual({ message: 'File size exceeds allowed file size limit (256 MB).' });
    });

    test('GET returns a list', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            }
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        const data = await response.json();
        expect(data).toBeInstanceOf(Array);
        expect(data.length).toBeGreaterThan(0);
        expect(data[0]).toHaveProperty('public_id');
        expect(data[0]).toHaveProperty('file_name');
    });

    test('GET without trailing slash returns a list', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        let response = await request.post(`${BASE_URL}/api/validationrequest`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            }
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        const data = await response.json();
        expect(data).toBeInstanceOf(Array);
        expect(data.length).toBeGreaterThan(0);
        expect(data[0]).toHaveProperty('public_id');
        expect(data[0]).toHaveProperty('file_name');
    });

});