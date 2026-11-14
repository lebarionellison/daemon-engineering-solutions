export default {
  async fetch(request) {
    const incoming = new URL(request.url);
    const destination = new URL(incoming.pathname + incoming.search, "https://daemon-engineering-solutions.lebarionellison.workers.dev");
    return Response.redirect(destination.toString(), 302);
  }
};
