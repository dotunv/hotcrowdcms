export type PlaylistStatus = "DRAFT" | "ACTIVE" | "SCHEDULED" | "ARCHIVED";
export type ScheduleType = "ALWAYS" | "SCHEDULED";
export type TransitionEffect = "NONE" | "FADE" | "SLIDE";

export type PlaylistItem = {
  id: number;
  media_id: string;
  url: string | null;
  type: string;
  duration: number;
  position: number;
  name: string;
};

export type PlaylistPayload = {
  id: string;
  name: string;
  status: PlaylistStatus;
  schedule_type: ScheduleType;
  start_date: string;
  end_date: string;
  start_time: string;
  end_time: string;
  transition_effect: TransitionEffect;
  is_loop: boolean;
  assigned_screen_ids: string[];
  items: PlaylistItem[];
  total_duration: number;
  item_count?: number;
};

export type MediaItem = {
  id: string;
  name: string;
  type: string;
  url: string | null;
  duration: number;
  media_type?: string;
};

export type ScreenItem = {
  id: string;
  name: string;
  location: string;
  online: boolean;
  playlist_id: string | null;
  playlist_name?: string | null;
  last_heartbeat?: string | null;
};

export type ScreenRow = ScreenItem;

export type Me = {
  id: number;
  username: string;
  email: string;
  plan?: string;
  store: {
    id: number;
    business_name: string;
    initials: string;
    description: string;
    phone_number: string;
    timezone: string;
    default_image_duration: number;
    transition_effect: string;
  };
  stores?: {
    id: number;
    business_name: string;
    initials: string;
    description: string;
    phone_number: string;
    timezone: string;
    default_image_duration: number;
    transition_effect: string;
  }[];
};

export type Dashboard = {
  store_name: string;
  initials: string;
  total_screens: number;
  online_screens: number;
  offline_screens: number;
  total_playlists: number;
  total_media: number;
  last_publish: string | null;
  last_heartbeat: string | null;
  screens: { id: string; name: string; online: boolean; playlist_name: string | null }[];
  recent_media: { id: string; name: string; type: string; url?: string | null }[];
};

export type StoreSettings = {
  id: number;
  business_name: string;
  initials: string;
  description: string;
  phone_number: string;
  timezone: string;
  branding_color: string;
  default_image_duration: number;
  transition_effect: string;
  mute_by_default: boolean;
  default_volume: number;
  fallback_type: string;
  fallback_logo: string;
  logo_url: string | null;
};

export type StoreLayout = {
  id: string;
  name: string;
  status: string;
  canvas_width: number;
  canvas_height: number;
  layout_data: {
    background?: { color?: string };
    elements?: {
      id: string;
      type: string;
      x: number;
      y: number;
      width: number;
      height: number;
      text?: string;
      fontSize?: number;
      color?: string;
      fill?: string;
      src?: string;
    }[];
  };
  published_media_id: string | null;
  preview_url: string;
};

export type Billing = {
  plan: string;
  label: string;
  stores: number;
  screens: number;
  instagram_sync: boolean;
  stripe_configured: boolean;
  plans: { id: string; label: string; stores: number; screens: number }[];
};
