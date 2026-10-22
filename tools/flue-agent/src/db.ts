import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sqlite } from '@flue/runtime/node';

const here = dirname(fileURLToPath(import.meta.url));

export default sqlite(resolve(here, '../.flue-data/huian-agent.db'));
