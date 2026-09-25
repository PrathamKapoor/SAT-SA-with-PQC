import { redirect } from "next/navigation";

// Temporary until the public surface is rebuilt (stage 12).
export default function Home() {
  redirect("/login");
}
