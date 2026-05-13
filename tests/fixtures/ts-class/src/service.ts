export interface User {
    id: number;
    name: string;
}

class UserService {
    private users: Map<number, User>;
    private static instance: UserService;

    constructor() {
        this.users = new Map();
    }

    async findById(id: number): Promise<User | undefined> {
        return this.users.get(id);
    }

    async create(data: Omit<User, 'id'>): Promise<User> {
        const id = Date.now();
        const user = { id, ...data };
        this.users.set(id, user);
        return user;
    }
}

function formatUserName(user: User): string {
    return user.name.toUpperCase();
}

const DEFAULT_PAGE_SIZE = 20;
let activeConnections = 0;
