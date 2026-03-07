
  # Meter Reading Interface

  This is a code bundle for Meter Reading Interface. The original project is available at https://www.figma.com/design/sI3nhBuio8bYNfI0VLd2Ue/Meter-Reading-Interface.

  ## Running the code

  Run `npm i` to install the dependencies.

  Run `npm run dev` to start the development server.

  ## API integration status

  The UI is wired to backend endpoints:
  - `POST /api/ocr`
  - `POST /api/readings`
  - `GET /api/readings`

  Vite dev server proxies `/api/*` to `http://127.0.0.1:8000` (see `vite.config.ts`).
  
