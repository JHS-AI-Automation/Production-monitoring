interface BrandConfig {
  appName: string;
  subtitle: string;
  footer: string;
  logo: string;
  colors: Record<string, string>;
  lineColors: readonly [string, string, string, string];
  chartAccent: string;
}
declare const brand: BrandConfig;
export default brand;
