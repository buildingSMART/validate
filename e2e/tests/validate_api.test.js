import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { basename } from 'path';

const BASE_URL = 'http://localhost:8000';
const TEST_CREDENTIALS = 'root:root';

function createAuthHeader(credentials) {

    const hash = Buffer.from(credentials).toString('base64');
    return {
        'Authorization': `Basic ${hash}`
    };
}

function createFormData(filePath, fileName = undefined) {

    const name = fileName ?? basename(filePath);
    const file = new File([readFileSync(filePath)], name);
    const form = new FormData();
    form.append('file', file);
    form.append('file_name', name);
    return form;
}

function createFormDataForTwoFiles(filePath1, filePath2) {

    const name1 = basename(filePath1);
    const file1 = new File([readFileSync(filePath1)], name1);
    const name2 = basename(filePath2);
    const file2 = new File([readFileSync(filePath2)], name2);

    const form = new FormData();
    form.append('file', file1);
    form.append('file_name', name1);
    form.append('file', file2);
    form.append('file_name', name2);
    return form;
}

function createDummyFormData(fileName, fileSize) {

    // create a buffer with zeros of specified size
    const largeBuffer = Buffer.alloc(fileSize, 0); 
    const file = new File([largeBuffer], fileName);
    const form = new FormData();
    form.append('file', file);
    form.append('file_name', fileName);
    return form;
}

test.describe('API - ValidationRequest', () => {

    test('POST accepts valid file', async ({ request }) => {

        // try to post a valid file
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST without trailing slash accepts valid file', async ({ request }) => {

        // try to post a valid file
        const response = await request.post(`${BASE_URL}/api/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST implements file size limit', async ({ request }) => {

        // try to post a large file
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createDummyFormData('very_large_file.ifc', 300 * 1024 * 1024) // 300 MB (> 256 MB limit)
        });

        // check if the response is correct - 413 Payload Too Large
        expect(response.statusText()).toBe('Request Entity Too Large');
        expect(response.status()).toBe(413); 

        // check if the error details are correct
        expect(await response.json()).toEqual({ message: 'File size exceeds allowed file size limit (256 MB).' });
    });

    test('POST rejects empty file', async ({ request }) => {

        // try to post an empty file
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/empty_file.ifc')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ file: [ 'The submitted file is empty.' ] });
    });

    test('POST rejects empty file name', async ({ request }) => {

        // try to post a file with empty filename
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/valid_file.ifc', '')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toStrictEqual({
            "file": [ "The submitted data was not a file. Check the encoding type on the form." ], 
            "file_name": [ "This field is required." ]
        });
    });

    test('POST only accepts *.ifc files', async ({ request }) => {

        // try to post a file with invalid file extension
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/invalid_file_extension')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ file_name: "File name must end with '.ifc'." });
    });

    test('POST only accepts a single file (for now)', async ({ request }) => {

        // try to post two valid files
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormDataForTwoFiles(
                'e2e/fixtures/valid_file.ifc', 
                'e2e/fixtures/valid_file2.ifc'
            )
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ message: 'Only one file can be uploaded at a time.' });
    });

    test('POST without authorization header returns 401', async ({ request }) => {

        // try to post a valid file but without authorization header
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
        });

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);
    });

    test('GET returns a list', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Array);
        expect(data.length).toBeGreaterThan(0);
        expect(data[0]).toHaveProperty('public_id');
        expect(data[0]).toHaveProperty('file_name');
    });

    test('GET without trailing slash returns a list', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Array);
        expect(data.length).toBeGreaterThan(0);
        expect(data[0]).toHaveProperty('public_id');
        expect(data[0]).toHaveProperty('file_name');
    });

    test('GET without authorization header returns 401', async ({ request }) => {

        // retrieve list of ValidationRequests
        const response = await request.get(`${BASE_URL}/api/validationrequest/`);

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);
    });

});