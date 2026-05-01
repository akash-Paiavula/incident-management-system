/**
 * Pages / Index
 * =============
 * Re-exports the root App component as the default page.
 * Acts as the routing entry point — if React Router is added later,
 * individual pages (Dashboard, Settings, etc.) would live alongside
 * this file and be registered in a <Routes> block here.
 *
 * Currently the entire IMS UI is a single-page dashboard,
 * so this simply re-exports App.
 */

export { default } from "../App.jsx";
