import { basename } from 'path';
import { statSync, readFileSync } from 'fs';



function createAuthHeader(credentials) {

    const hash = Buffer.from(credentials).toString('base64');
    return {
        'Authorization': `Basic ${hash}`
    };
}

function createFormData(filePath, fileName = undefined) {

    const name = fileName ?? basename(filePath);
    const file = new File([findAndReadFileSync(filePath)], name);
    const form = new FormData();
    form.append('file', file);
    form.append('file_name', name);
    return form;
}

function findAndReadFileSync(filepath) {
    
    if (statSync(filepath, { throwIfNoEntry: false })?.isFile()) {
        return readFileSync(filepath);        
    } else if (statSync('e2e/' + filepath, { throwIfNoEntry: false })?.isFile()) {
        return readFileSync('e2e/' + filepath);
    }
    throw new Error(`File does not exist: ${filepath}`);
}

export { createAuthHeader, createFormData };