import {parse} from "cookie"

export default function adminpageprotection(request, response) {
    const cookies = parse(request.headers.cookies || "")
    const role = cookies.userRole

    if (!role || role !== "admin") {
        return response.status(403).json({message: "Forbidden"})
    }

    return response.status(200).json({message: "You are an admin!"})
}