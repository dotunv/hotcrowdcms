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
