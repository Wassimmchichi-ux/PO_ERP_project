export const appInfo = {
  productName: "Adient ERP",
  companyName: "Wassim Mchichi",
  clientName: "Adient",
  version: "0.1.0-prototype",
  productTagline: "Configurable ERP prototype",
  logoSrc: "/adient-logo.png",
  logoInverseSrc: "/adient-logo-inverse.png",
  faviconSrc: "/adient-favicon.png",
} as const;

export function pageTitle(section?: string): string {
  return section ? `${section} - ${appInfo.productName}` : appInfo.productName;
}

export const poweredByText = `Powered by ${appInfo.companyName}`;

export const footerSignature = `${appInfo.productName} • Developed by ${appInfo.companyName}`;
